"""TS classification and other functions
"""
import functools
import itertools
import warnings
from typing import Dict, Optional, Tuple

import numpy
from automol import util
from automol.graph.base._00core import (
    AtomKey,
    BondKey,
    atom_implicit_hydrogens,
    atom_neighbor_atom_keys,
    bond_neighbor_atom_keys,
    is_ts_graph,
    local_stereo_priorities,
    tetrahedral_atom_keys,
    ts_breaking_bond_keys,
    ts_forming_bond_keys,
    ts_reactants_graph_without_stereo,
    ts_reagents_graphs_without_stereo,
    ts_reverse,
    vinyl_center_candidates,
    without_bonds_by_orders,
    without_dummy_atoms,
)
from automol.graph.base._02algo import reacting_rings_bond_keys
from automol.util import dict_


# reaction site classification
def atom_transfers(tsg) -> Dict[int, Tuple[int, int]]:
    """Get a dictionary describing atom transfers; keys are transferring atoms, values
    are donors and acceptors, respectively

    :param tsg: TS graph
    :type tsg: automol graph data structure
    :returns: A list of triples containing the donor atom, the transferring atom, and
        the acceptor atom, respectively
    :rtype: Dict[int, Tuple[int, int]]
    """
    brk_bkeys = ts_breaking_bond_keys(tsg)
    frm_bkeys = ts_forming_bond_keys(tsg)

    tra_dct = {}
    for brk_bkey, frm_bkey in itertools.product(brk_bkeys, frm_bkeys):
        if brk_bkey & frm_bkey:
            (tra_key,) = brk_bkey & frm_bkey
            (don_key,) = brk_bkey - frm_bkey
            (acc_key,) = frm_bkey - brk_bkey
            tra_dct[tra_key] = (don_key, acc_key)

    return tra_dct


def substitutions(tsg) -> Dict[int, Tuple[int, int]]:
    """Get a dictionary describing substitution reaction sites

    Maps transferring atoms onto their leaving and entering atoms, respectively

    (Limited to substitutions at tetrahedral atoms)

    :param tsg: TS graph
    :type tsg: automol graph data structure
    :returns: A mapping of transferring atoms onto leaving and entering atoms
    :rtype: Dict[int, Tuple[int, int]]
    """
    tra_dct = atom_transfers(tsg)
    tra_keys = set(tra_dct.keys())
    tet_keys = tetrahedral_atom_keys(tsg)
    subst_keys = tra_keys & tet_keys
    return util.dict_.by_key(tra_dct, subst_keys)


def vinyl_addition_candidates(
    tsg, min_ncount: int = 1
) -> Dict[BondKey, Tuple[AtomKey, AtomKey]]:
    """Get a dictionary describing vinyl addition reaction site *candidates*

    Maps vinyl bond keys onto vinyl radical atoms entering atoms, respectively

    (Only finds candidates, since resonance evaluation is expensive)

    :param tsg: TS graph
    :type tsg: automol graph data structure
    :param min_ncount: Minimal # neighbor keys for consideration
    :type min_ncount: int, optional
    :returns: A mapping of transferring atoms onto leaving and entering atoms
    """
    rcts_gra = ts_reactants_graph_without_stereo(tsg)

    frm_bkeys = ts_forming_bond_keys(tsg)
    vin_dct = vinyl_center_candidates(rcts_gra, min_ncount=min_ncount)

    vin_add_dct = {}
    for key, bkey in vin_dct.items():
        # Find a forming bond at the vinyl radical site
        frm_bkey = next((bk for bk in frm_bkeys if key in bk), None)
        if frm_bkey is not None:
            (ent_key,) = frm_bkey - {key}

            vin_add_dct[bkey] = (key, ent_key)
    return vin_add_dct


def eliminations(tsg) -> Dict[BondKey, Tuple[AtomKey, AtomKey, Optional[BondKey]]]:
    """Get a dictionary describing elimination reaction sites

    Maps bonds across which eliminations occur onto their leaving atoms, along with the
    forming bond key for each, if present

    :param tsg: TS graph
    :type tsg: automol graph data structure
    :returns: A mapping of elimination bonds onto leaving atoms and forming bond keys
        (Leaving atoms are sorted in order of the elimination bond atoms)
    """
    brk_bkeys_pool = ts_breaking_bond_keys(tsg)
    frm_bkeys_pool = ts_forming_bond_keys(tsg)
    rng_bkeys_lst = reacting_rings_bond_keys(tsg)

    def is_elimination_bond_(brk_bkeys, frm_bkeys):
        """An elimination bond key is a ring key that intersects two breaking bonds and
        is not a forming bond
        """

        def is_elimination_bkey(bkey):
            return all(bkey & bk for bk in brk_bkeys) and bkey not in frm_bkeys

        return is_elimination_bkey

    def common_atom(bkey1, bkey2):
        return next(iter(bkey1 & bkey2))

    # 1. Check reacting rings
    elim_dct = {}
    for rng_bkeys in rng_bkeys_lst:
        brk_bkeys = brk_bkeys_pool & rng_bkeys
        frm_bkeys = frm_bkeys_pool & rng_bkeys

        # 2. Require two breaking bonds within the ring
        if len(brk_bkeys) == 2:
            # 3. Find the elimination bond
            is_elim = is_elimination_bond_(brk_bkeys, frm_bkeys)
            bkey = next(filter(is_elim, rng_bkeys), None)
            if bkey is not None:
                # a. Sort the breaking bonds in order of the elimination bond atom
                brk_bkey1, brk_bkey2 = sorted(
                    brk_bkeys, key=functools.partial(common_atom, bkey)
                )

                # b. Get the corresponding leaving atoms
                (lea_key1,) = brk_bkey1 - bkey
                (lea_key2,) = brk_bkey2 - bkey

                # c. Get the forming bond key, if there is one
                assert len(frm_bkeys) <= 1, "Unexpected multiple forming bonds:{tsg}"
                frm_bkey = next(iter(frm_bkeys), None)

                elim_dct[bkey] = (lea_key1, lea_key2, frm_bkey)

    return elim_dct


def insertions(tsg) -> Dict[int, Tuple[int, int]]:
    """Get a dictionary describing insertion reaction sites

    Maps bonds across which insertions occur onto their entering atoms, along with the
    breaking bond key for each, if present

    :param tsg: TS graph
    :type tsg: automol graph data structure
    :returns: A mapping of insertion bonds onto entering atoms and breaking bond keys
        (Entering atoms are sorted in order of the insertion bond atoms)
    :rtype: Dict[int, Tuple[int, int]]
    """
    return eliminations(ts_reverse(tsg))


# vvv DEPRECATED vvv
def atom_stereo_sorted_neighbor_keys(
    gra, key, self_apex: bool = False, pri_dct: Optional[Dict[int, int]] = None
):
    """Get keys for the neighbors of an atom that are relevant for atom
    stereochemistry, sorted by priority (if requested)

    :param gra: molecular graph
    :type gra: automol graph data structure
    :param key: the atom key
    :type key: int
    :param self_apex: If there are only 3 neighbors, put this atom as the apex?
    :type self_apex: bool, optional
    :param pri_dct: Priorities to sort by (optional)
    :type pri_dct: Optional[Dict[int, int]]
    :returns: The keys of neighboring atoms
    :rtype: tuple[int]
    """
    gra = without_dummy_atoms(gra)
    nhyd_dct = atom_implicit_hydrogens(gra)
    pri_dct = local_stereo_priorities(gra) if pri_dct is None else pri_dct

    # If this is an Sn2 stereocenter, use the reactants graph
    if key in substitutions(gra):
        gra = ts_reactants_graph_without_stereo(gra)

    # Get the neighboring atom keys
    nkeys = list(atom_neighbor_atom_keys(gra, key))

    # Add Nones for the implicit hydrogens
    nkeys.extend([None] * nhyd_dct[key])

    # Sort them by priority
    nkeys = sorted(nkeys, key=dict_.sort_value_(pri_dct, missing_val=-numpy.inf))

    # Optionally, if there are only three groups, use the stereo atom itself as
    # the top apex of the tetrahedron
    if self_apex and len(nkeys) < 4:
        assert len(nkeys) == 3
        nkeys = [key] + list(nkeys)

    return tuple(nkeys)


def bond_stereo_sorted_neighbor_keys(
    gra, key1, key2, pri_dct: Optional[Dict[int, int]] = None
):
    """Get keys for the neighbors of a bond that are relevant for bond
    stereochemistry, sorted by priority (if requested)

    :param gra: molecular graph
    :type gra: automol graph data structure
    :param key1: the first atom in the bond
    :type key1: int
    :param key2: the second atom in the bond
    :type key2: int
    :param pri_dct: Priorities to sort by (optional)
    :type pri_dct: Optional[Dict[int, int]]
    :returns: The keys of neighboring atoms for the first and second atoms
    :rtype: tuple[int], tuple[int]
    """
    gra = without_dummy_atoms(gra)
    nhyd_dct = atom_implicit_hydrogens(gra)
    pri_dct = local_stereo_priorities(gra) if pri_dct is None else pri_dct

    gras = ts_reagents_graphs_without_stereo(gra) if is_ts_graph(gra) else [gra]

    nkeys1 = set()
    nkeys2 = set()
    # For TS graphs, loop over reactants and products
    for gra_ in gras:
        # Check that the bond is rigid and planar on this side of the reaction, by
        # checking for a tetrahedral atom
        tet_keys = tetrahedral_atom_keys(gra_)
        if key1 not in tet_keys and key2 not in tet_keys:
            # Add these neighboring keys to the list
            nkeys1_, nkeys2_ = bond_neighbor_atom_keys(gra_, key1, key2)
            nkeys1.update(nkeys1_)
            nkeys2.update(nkeys2_)

    nkeys1 = list(nkeys1)
    nkeys2 = list(nkeys2)
    nkeys1.extend([None] * nhyd_dct[key1])
    nkeys2.extend([None] * nhyd_dct[key2])

    # Check that we don't have more than two neighbors on either side
    if len(nkeys1) > 2 or len(nkeys2) > 2:
        warnings.warn(
            f"Unusual neighbor configuration at bond {key1}-{key2} may result in "
            f"incorrect bond stereochemistry handling for this graph:\n{gra}"
        )

        # Temporary patch for misidentified substitutions at double bonds, which are
        # really two-step addition-eliminations
        gra_ = without_bonds_by_orders(gra, [0.1, 0.9])
        nkeys1, nkeys2 = map(list, bond_neighbor_atom_keys(gra_, key1, key2))
        nkeys1.extend([None] * nhyd_dct[key1])
        nkeys2.extend([None] * nhyd_dct[key2])

    nkeys1 = sorted(nkeys1, key=dict_.sort_value_(pri_dct, missing_val=-numpy.inf))
    nkeys2 = sorted(nkeys2, key=dict_.sort_value_(pri_dct, missing_val=-numpy.inf))
    return (tuple(nkeys1), tuple(nkeys2))
