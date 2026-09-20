"""Six-DOF node mapping and dense assembly, matching the frame2d API style."""

import numpy as np

from .models import array, identifier


def calculate_node_dof_map(node_id):
    identifier("node_id", node_id)
    return np.arange(6 * (node_id - 1), 6 * node_id, dtype=int)


def calculate_element_dof_map(element):
    return np.concatenate(
        [calculate_node_dof_map(element.node_i), calculate_node_dof_map(element.node_j)]
    )


def assemble_global_stiffness(number_of_nodes, contributions):
    identifier("number_of_nodes", number_of_nodes)
    k = np.zeros((6 * number_of_nodes, 6 * number_of_nodes))
    for element, matrix in contributions:
        dofs = calculate_element_dof_map(element)
        if dofs.max() >= len(k):
            raise ValueError("element references an unknown node")
        k[np.ix_(dofs, dofs)] += array("element stiffness", matrix, (12, 12))
    return k


def assemble_nodal_load_vector(number_of_nodes, loads):
    identifier("number_of_nodes", number_of_nodes)
    f = np.zeros(6 * number_of_nodes)
    for load in loads:
        if load.node_id > number_of_nodes:
            raise ValueError("nodal load references an unknown node")
        f[calculate_node_dof_map(load.node_id)] += load.vector
    return f


def assemble_equivalent_nodal_load_vector(number_of_nodes, contributions):
    identifier("number_of_nodes", number_of_nodes)
    f = np.zeros(6 * number_of_nodes)
    for element, vector in contributions:
        dofs = calculate_element_dof_map(element)
        if dofs.max() >= len(f):
            raise ValueError("element references an unknown node")
        f[dofs] += array("equivalent load", vector, (12,))
    return f
