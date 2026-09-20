"""A00: d_local=T d_global, K_global=T.T K_local T."""

import numpy as np

from .models import array, basis


def calculate_transformation(geometry):
    return np.kron(np.eye(4), basis(geometry.Q))


def calculate_global_stiffness(local_stiffness, transformation):
    k = array("local_stiffness", local_stiffness, (12, 12))
    t = array("transformation", transformation, (12, 12))
    return t.T @ k @ t


def calculate_global_equivalent_nodal_load(local_load, transformation):
    return array("transformation", transformation, (12, 12)).T @ array(
        "local_load", local_load, (12,)
    )
