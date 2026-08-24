"""Adapter for the installed ``continuum-math`` 0.7 public API."""

from __future__ import annotations

from typing import Any

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
from nonlinear_core.model import LoadKind, ModelFamily, ModelInput


class ContinuumAdapter(LinearCoreAdapter):
    family = ModelFamily.CONTINUUM
    adapter_id = "continuum-math-linear"
    core_package = "continuum-math"
    core_version = "0.7.0"

    def _build_native_system(self, model: ModelInput) -> NativeSystem:
        self._require_family(model)
        from continuum_math import (
            BodyForce,
            BoundaryCondition,
            DofComponent,
            EdgeTraction,
            Element,
            Material2D,
            Model,
            NodalLoad,
            Node,
            PlaneMode,
            Q4Element,
            assemble,
            element_body_force,
            element_dofs,
            element_edge_force,
            element_stiffness,
            q4_diagnostics,
            t3_signed_area,
        )

        node_indices = node_index_lookup(model)
        native_nodes = tuple(
            Node(index, (float(node.coordinates[0]), float(node.coordinates[1])))
            for index, node in enumerate(model.nodes)
        )
        materials = material_lookup(model)
        native_elements: list[Any] = []
        native_element_ids: dict[str, int] = {}
        for index, element in enumerate(model.elements):
            material_input = materials[element.material_id]
            parameters = material_input.parameters
            native_material = Material2D(
                E=float_value(parameters, "young", "young_modulus", "E"),
                nu=float_value(parameters, "poisson", "poisson_ratio", "nu"),
                mode=PlaneMode(str(parameters.get("plane_mode", "plane_stress"))),
            )
            connectivity = tuple(node_indices[node_id] for node_id in element.node_ids)
            thickness = float_value(element.properties, "thickness", default=1.0)
            formulation = element.formulation.strip().lower()
            native_element_ids[element.id] = index
            if "t3" in formulation or len(connectivity) == 3:
                if len(connectivity) != 3:
                    raise ValueError(f"continuum element {element.id!r} requires 3 nodes")
                native_elements.append(Element(index, connectivity, native_material, thickness))
            elif "q4" in formulation or len(connectivity) == 4:
                if len(connectivity) != 4:
                    raise ValueError(f"continuum element {element.id!r} requires 4 nodes")
                native_elements.append(Q4Element(index, connectivity, native_material, thickness))
            else:
                raise ValueError(
                    f"unsupported continuum formulation {element.formulation!r}; use T3 or Q4"
                )

        nodal_loads = []
        body_forces = []
        edge_tractions = []
        for load in model.loads:
            components = scaled_components(load)
            if load.kind is LoadKind.NODAL:
                assert load.node_id is not None
                nodal_loads.append(
                    NodalLoad(
                        node_indices[load.node_id],
                        (components.get("UX", 0.0), components.get("UY", 0.0)),
                    )
                )
            elif load.kind is LoadKind.BODY:
                density = (components.get("UX", 0.0), components.get("UY", 0.0))
                body_forces.extend(
                    BodyForce(native_element_ids[element.id], density) for element in model.elements
                )
            elif load.kind is LoadKind.EDGE:
                assert load.element_id is not None
                raw_edge = load.extensions.get("edge_node_ids")
                if not isinstance(raw_edge, list) or len(raw_edge) != 2:
                    raise ValueError(
                        f"edge load {load.id!r} requires extensions.edge_node_ids with 2 nodes"
                    )
                edge_tractions.append(
                    EdgeTraction(
                        native_element_ids[load.element_id],
                        (node_indices[str(raw_edge[0])], node_indices[str(raw_edge[1])]),
                        (components.get("UX", 0.0), components.get("UY", 0.0)),
                    )
                )
            else:
                raise ValueError(
                    f"continuum adapter does not support {load.kind.value!r} load {load.id!r}"
                )

        component_map = {"UX": DofComponent.U, "UY": DofComponent.V}
        boundary_conditions = tuple(
            BoundaryCondition(
                node_indices[constraint.node_id],
                component_map[constraint.dof.value],
                float(constraint.value),
            )
            for constraint in model.constraints
        )
        native_model = Model(
            nodes=native_nodes,
            elements=tuple(native_elements),
            nodal_loads=tuple(nodal_loads),
            body_forces=tuple(body_forces),
            edge_tractions=tuple(edge_tractions),
            boundary_conditions=boundary_conditions,
        )
        stiffness, force = assemble(native_model)

        connected_owner = first_connected_elements(model)
        element_forces = {
            element.id: np.zeros(2 * len(element.node_ids), dtype=float)
            for element in model.elements
        }
        for load in model.loads:
            components = scaled_components(load)
            if load.kind is LoadKind.NODAL:
                assert load.node_id is not None
                owner_id = connected_owner[load.node_id]
                owner = next(item for item in model.elements if item.id == owner_id)
                local_node = owner.node_ids.index(load.node_id)
                element_forces[owner_id][2 * local_node : 2 * local_node + 2] += (
                    components.get("UX", 0.0),
                    components.get("UY", 0.0),
                )

        coordinates = native_model.coordinates
        normalized_elements: list[NativeElement] = []
        for common_element, native_element in zip(
            model.elements, native_model.elements, strict=True
        ):
            local_coordinates = coordinates[np.asarray(native_element.connectivity)]
            local_force = element_forces[common_element.id]
            for body in native_model.body_forces:
                if body.element_id == native_element.id:
                    local_force += element_body_force(
                        native_element, local_coordinates, body.force_density
                    )
            for edge in native_model.edge_tractions:
                if edge.element_id == native_element.id:
                    local_force += element_edge_force(
                        native_element, local_coordinates, edge.edge, edge.traction
                    )
            local_stiffness = element_stiffness(native_element, local_coordinates)
            if isinstance(native_element, Q4Element):
                min_det_j = q4_diagnostics(
                    local_coordinates, native_element.material, native_element.thickness
                ).minimum_detJ
            else:
                min_det_j = 2.0 * t3_signed_area(local_coordinates)
            normalized_elements.append(
                NativeElement(
                    element_id=common_element.id,
                    dof_indices=tuple(
                        int(value) for value in element_dofs(native_element.connectivity)
                    ),
                    stiffness=local_stiffness,
                    force=local_force,
                    min_det_j=float(min_det_j),
                    metadata={"formulation": native_element.kind},
                )
            )
        return NativeSystem(
            stiffness=stiffness,
            force=force,
            elements=tuple(normalized_elements),
            native_model=native_model,
        )

    def native_reference(self, model: ModelInput) -> AdapterRecovery:
        from continuum_math import solve_model

        system = self._build_native_system(model)
        solved = solve_model(system.native_model)
        return AdapterRecovery(
            displacement=solved.displacement,
            reactions=solved.reactions,
            strain_energy=float(solved.global_energy),
            element_data=tuple(
                {"element_id": str(element_id), "energy": float(energy)}
                for element_id, energy in solved.element_energies
            ),
            metadata={
                "core_package": self.core_package,
                "free_residual_norm": solved.diagnostics.free_residual_norm,
            },
        )


__all__ = ["ContinuumAdapter"]
