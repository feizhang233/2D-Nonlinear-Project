"""A02 end actions: original k d - f, after release back-substitution."""

from dataclasses import dataclass

import numpy as np

from .assembly import calculate_element_dof_map
from .models import array


@dataclass(frozen=True, slots=True)
class ElementEndResponse:
    global_displacements: np.ndarray
    local_displacements: np.ndarray
    local_end_forces: np.ndarray


def extract_element_displacements(element, displacements):
    d = np.asarray(displacements, dtype=float)
    if d.ndim != 1 or not d.size or d.size % 6 or not np.isfinite(d).all():
        raise ValueError("displacements must be a finite 6-DOF/node vector")
    dofs = calculate_element_dof_map(element)
    if dofs.max() >= len(d):
        raise ValueError("element references an unknown node")
    return d[dofs].copy()


def recover_local_displacements(element_displacements, transformation):
    return array("transformation", transformation, (12, 12)) @ array(
        "element_displacements", element_displacements, (12,)
    )


def recover_local_end_forces(
    local_stiffness, local_displacements, local_equivalent_nodal_load=None
):
    f = (
        np.zeros(12)
        if local_equivalent_nodal_load is None
        else array("local_equivalent_nodal_load", local_equivalent_nodal_load, (12,))
    )
    return (
        array("local_stiffness", local_stiffness, (12, 12))
        @ array("local_displacements", local_displacements, (12,))
        - f
    )


def recover_element_end_response(
    element,
    displacements,
    local_stiffness,
    transformation,
    local_equivalent_nodal_load=None,
    *,
    condensation=None,
):
    dg = extract_element_displacements(element, displacements)
    dl = recover_local_displacements(dg, transformation)
    if element.releases and condensation is None:
        raise ValueError("released elements require condensation data for recovery")
    if condensation is not None:
        dl = condensation.recover(dl)
    return ElementEndResponse(
        dg, dl, recover_local_end_forces(local_stiffness, dl, local_equivalent_nodal_load)
    )
