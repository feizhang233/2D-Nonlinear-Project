"""Adapter for the installed ``frame2d`` 0.2 public API."""

from __future__ import annotations

import numpy as np

from nonlinear_core.adapters._mapping import (
    first_connected_elements,
    float_value,
    material_lookup,
    node_index_lookup,
    scaled_components,
)
from nonlinear_core.adapters.base import (
    AdapterRecovery,
    LinearCoreAdapter,
    NativeElement,
    NativeSystem,
)
from nonlinear_core.model import CoordinateSystem, LoadKind, ModelFamily, ModelInput


class FrameAdapter(LinearCoreAdapter):
    family = ModelFamily.FRAME
    adapter_id = "frame2d-linear"
    core_package = "frame2d"
    core_version = "0.2.0"

    def _build_native_system(self, model: ModelInput) -> NativeSystem:
        self._require_family(model)
        from frame2d import (
            DistributedLoad,
            FrameElement,
            NodalLoad,
            Node,
            Support,
            assemble_equivalent_nodal_load_vector,
            assemble_global_stiffness,
            assemble_nodal_load_vector,
            calculate_element_dof_map,
            calculate_geometry,
            calculate_global_equivalent_nodal_load,
            calculate_global_stiffness,
            calculate_local_equivalent_nodal_load,
            calculate_local_stiffness,
            calculate_transformation,
        )

        node_indices = node_index_lookup(model)
        native_nodes = tuple(
            Node(index + 1, float(node.coordinates[0]), float(node.coordinates[1]))
            for index, node in enumerate(model.nodes)
        )
        nodes_by_id = {node.id: node for node in native_nodes}
        materials = material_lookup(model)
        native_elements = []
        native_element_ids: dict[str, int] = {}
        for index, element in enumerate(model.elements):
            if len(element.node_ids) != 2:
                raise ValueError(f"frame element {element.id!r} requires exactly 2 nodes")
            formulation = element.formulation.strip().lower()
            if "frame" not in formulation and "beam" not in formulation:
                raise ValueError(
                    f"unsupported frame formulation {element.formulation!r}; use frame2d"
                )
            material = materials[element.material_id]
            native_id = index + 1
            native_element_ids[element.id] = native_id
            native_elements.append(
                FrameElement(
                    native_id,
                    node_indices[element.node_ids[0]] + 1,
                    node_indices[element.node_ids[1]] + 1,
                    float_value(material.parameters, "young", "young_modulus", "E"),
                    float_value(element.properties, "area", "A"),
                    float_value(
                        element.properties,
                        "second_moment",
                        "moment_of_inertia",
                        "I",
                    ),
                )
            )

        nodal_loads = []
        distributed_loads = []
        for load in model.loads:
            components = scaled_components(load)
            if load.kind is LoadKind.NODAL:
                assert load.node_id is not None
                nodal_loads.append(
                    NodalLoad(
                        node_indices[load.node_id] + 1,
                        fx=components.get("UX", 0.0),
                        fy=components.get("UY", 0.0),
                        mz=components.get("RZ", 0.0),
                    )
                )
            elif load.kind in {LoadKind.ELEMENT, LoadKind.EDGE}:
                if load.coordinate_system is not CoordinateSystem.LOCAL:
                    raise ValueError(
                        f"frame distributed load {load.id!r} must use coordinate_system='local'"
                    )
                assert load.element_id is not None
                qx_i = components.get("qx_i", components.get("UX", 0.0))
                qy_i = components.get("qy_i", components.get("UY", 0.0))
                distributed_loads.append(
                    DistributedLoad(
                        native_element_ids[load.element_id],
                        qx_i=qx_i,
                        qy_i=qy_i,
                        qx_j=components.get("qx_j", qx_i),
                        qy_j=components.get("qy_j", qy_i),
                    )
                )
            else:
                raise ValueError(
                    f"frame adapter does not support {load.kind.value!r} load {load.id!r}"
                )

        constraints_by_node: dict[str, dict[str, float]] = {}
        for constraint in model.constraints:
            constraints_by_node.setdefault(constraint.node_id, {})[constraint.dof.value] = float(
                constraint.value
            )
        supports = tuple(
            Support(
                node_id=node_indices[node_id] + 1,
                u="UX" in values,
                v="UY" in values,
                phi="RZ" in values,
                u_value=values.get("UX", 0.0),
                v_value=values.get("UY", 0.0),
                phi_value=values.get("RZ", 0.0),
            )
            for node_id, values in constraints_by_node.items()
        )

        stiffness_contributions = []
        equivalent_contributions = []
        element_operators: dict[int, tuple[np.ndarray, np.ndarray, float]] = {}
        loads_by_element: dict[int, list[object]] = {element.id: [] for element in native_elements}
        for load in distributed_loads:
            loads_by_element[load.element_id].append(load)
        for element in native_elements:
            geometry = calculate_geometry(
                element,
                nodes_by_id[element.node_i],
                nodes_by_id[element.node_j],
            )
            local_stiffness = calculate_local_stiffness(element, geometry.L)
            transformation = calculate_transformation(geometry)
            global_stiffness = calculate_global_stiffness(local_stiffness, transformation)
            global_force = np.zeros(6, dtype=float)
            for load in loads_by_element[element.id]:
                local_force = calculate_local_equivalent_nodal_load(element, load, geometry.L)
                global_force += calculate_global_equivalent_nodal_load(local_force, transformation)
            stiffness_contributions.append((element, global_stiffness))
            equivalent_contributions.append((element, global_force))
            element_operators[element.id] = (global_stiffness, global_force, geometry.L)

        stiffness = assemble_global_stiffness(len(native_nodes), stiffness_contributions)
        force = assemble_nodal_load_vector(len(native_nodes), nodal_loads)
        force += assemble_equivalent_nodal_load_vector(len(native_nodes), equivalent_contributions)

        connected_owner = first_connected_elements(model)
        local_nodal_forces = {element.id: np.zeros(6, dtype=float) for element in model.elements}
        for load in model.loads:
            if load.kind is not LoadKind.NODAL:
                continue
            assert load.node_id is not None
            owner_id = connected_owner[load.node_id]
            owner = next(item for item in model.elements if item.id == owner_id)
            local_node = owner.node_ids.index(load.node_id)
            components = scaled_components(load)
            local_nodal_forces[owner_id][3 * local_node : 3 * local_node + 3] += (
                components.get("UX", 0.0),
                components.get("UY", 0.0),
                components.get("RZ", 0.0),
            )

        normalized_elements = []
        for common, native in zip(model.elements, native_elements, strict=True):
            local_stiffness, local_force, length = element_operators[native.id]
            normalized_elements.append(
                NativeElement(
                    element_id=common.id,
                    dof_indices=tuple(int(value) for value in calculate_element_dof_map(native)),
                    stiffness=local_stiffness,
                    force=local_force + local_nodal_forces[common.id],
                    min_det_j=None,
                    metadata={"formulation": "frame2d", "length": float(length)},
                )
            )
        return NativeSystem(
            stiffness=stiffness,
            force=force,
            elements=tuple(normalized_elements),
            native_model=(
                native_nodes,
                tuple(native_elements),
                supports,
                tuple(nodal_loads),
                tuple(distributed_loads),
            ),
        )

    def native_reference(self, model: ModelInput) -> AdapterRecovery:
        from frame2d import solve_frame

        system = self._build_native_system(model)
        nodes, elements, supports, nodal_loads, distributed_loads = system.native_model
        solved = solve_frame(
            nodes,
            elements,
            supports,
            nodal_loads,
            distributed_loads,
            number_of_points=3,
        )
        energy = float(0.5 * solved.displacements @ system.stiffness @ solved.displacements)
        return AdapterRecovery(
            displacement=solved.displacements,
            reactions=solved.reactions,
            strain_energy=energy,
            element_data=tuple(
                {
                    "element_id": str(item.element_id),
                    "equilibrium_passed": item.validation.passed,
                }
                for item in solved.elements
            ),
            metadata={
                "core_package": self.core_package,
                "global_validation_passed": solved.validation.passed,
            },
        )


__all__ = ["FrameAdapter"]
