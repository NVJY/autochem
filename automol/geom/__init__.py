""" a cartesian geometry module
"""
from ..constructors.geom import from_data
from ._core import symbols
from ._core import coordinates
from ._core import set_coordinates
from ._core import is_valid
from ._comp import almost_equal
from ._comp import almost_equal_coulomb_spectrum
from ._comp import argunique_coulomb_spectrum
from ._zmatrix import zmatrix
from ._zmatrix import zmatrix_torsion_coordinate_names
from ._zmatrix import distance
from ._zmatrix import angle
from ._zmatrix import dihedral
from ._graph import connectivity_graph
from ._inchi import inchi
from ._io import string
from ._io import from_string
from ._io import xyz_string
from ._io import xyz_trajectory_string
from ._io import from_xyz_string
from ._repr import formula
from ._repr import coulomb_spectrum
from ._trans import rotate


__all__ = [
    'from_data',
    'symbols',
    'coordinates',
    'set_coordinates',
    'is_valid',
    'almost_equal',
    'almost_equal_coulomb_spectrum',
    'argunique_coulomb_spectrum',
    'zmatrix',
    'zmatrix_torsion_coordinate_names',
    'distance',
    'angle',
    'dihedral',
    'connectivity_graph',
    'inchi',
    'string',
    'from_string',
    'xyz_string',
    'xyz_trajectory_string',
    'from_xyz_string',
    'formula',
    'coulomb_spectrum',
    'rotate',
]
