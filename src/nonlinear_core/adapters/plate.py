"""Adapter for the installed ``mindlin-plate-core`` 0.3 public API."""

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
from nonlinear_core.model import LoadKind, ModelFamily, ModelInput


class PlateAdapter(LinearCoreAdapter):
    family = ModelFamily.PLATE
    adapter_id = "mindlin-plate-linear"
    core_package = "mindlin-plate-core"
    core_version = "0.3.0"

    def _build_native_system(self, model: ModelInput) -> NativeSystem:
        self._require_family(model)
        from mindlin_plate import (
            Mesh,
            MindlinMaterial,
            kinematic_matrices,
            plate_element_matrices,
            q4_consistent_load,
            q4_edge_consistent_load,
        )

        node_indices = node_index_lookup(model)
        nodes = np.asarray(
            [[float(node.coordinates[0]), float(node.coordinates[1])] for node in model.nodes],
            dtype=float,
        )
        connectivities = []
        for element in model.elements:
            if len(element.node_ids) != 4:
                raise ValueError(f"plate element {element.id!r} requires exactly 4 nodes")
            formulation = element.formulation.strip().lower()
            if "q4" not in formulation and "plate" not in formulation:
                raise ValueError(
                    f"unsupported plate formulation {element.formulation!r}; use Q4 plate"
                )
            connectivities.append(tuple(node_indices[node_id] for node_id in element.node_ids))
        mesh = Mesh(nodes, np.asarray(connectivities, dtype=np.int64))
        materials = material_lookup(model)

        size = mesh.ndof
        stiffness = np.zeros((size, size), dtype=float)
        force = np.zeros(size, dtype=float)
        element_forces = {element.id: np.zeros(12, dtype=float) for element in model.elements}
        surface_loads: dict[str, float] = {element.id: 0.0 for element in model.elements}
        edge_loads: dict[str, list[tuple[int, float, tuple[float, float]]]] = {
            element.id: [] for element in model.elements
        }
        for load in model.loads:
            components = scaled_components(load)
            if load.kind is LoadKind.SURFACE:
                assert load.element_id is not None
                surface_loads[load.element_id] += components.get("UZ", 0.0)
            elif load.kind is LoadKind.EDGE:
                assert load.element_id is not None
                raw_edge = load.extensions.get("local_edge")
                if isinstance(raw_edge, bool) or not isinstance(raw_edge, int):
                    raise ValueError(
                        f"plate edge load {load.id!r} requires integer extensions.local_edge"
                    )
                edge_loads[load.element_id].append(
                    (
                        raw_edge,
                        components.get("UZ", 0.0),
                        (components.get("RX", 0.0), components.get("RY", 0.0)),
                    )
                )
            elif load.kind is not LoadKind.NODAL:
                raise ValueError(
                    f"plate adapter does not support {load.kind.value!r} load {load.id!r}"
                )

        connected_owner = first_connected_elements(model)
        for load in model.loads:
            if load.kind is not LoadKind.NODAL:
                continue
            assert load.node_id is not None
            owner_id = connected_owner[load.node_id]
            owner = next(item for item in model.elements if item.id == owner_id)
            local_node = owner.node_ids.index(load.node_id)
            components = scaled_components(load)
            values = np.asarray(
                [
                    components.get("UZ", 0.0),
                    components.get("RX", 0.0),
                    components.get("RY", 0.0),
                ]
            )
            global_node = node_indices[load.node_id]
            force[3 * global_node : 3 * global_node + 3] += values
            element_forces[owner_id][3 * local_node : 3 * local_node + 3] += values

        normalized_elements = []
        for index, (common, connectivity) in enumerate(
            zip(model.elements, mesh.elements, strict=True)
        ):
            material_input = materials[common.material_id]
            material = MindlinMaterial(
                young=float_value(material_input.parameters, "young", "young_modulus", "E"),
                poisson=float_value(material_input.parameters, "poisson", "poisson_ratio", "nu"),
                thickness=float_value(common.properties, "thickness"),
                shear_correction=float_value(
                    common.properties,
                    "shear_correction",
                    "shear_correction_factor",
                    default=5.0 / 6.0,
                ),
            )
            plate_method = str(common.properties.get("plate_method", "M"))
            shear_scheme = str(common.properties.get("shear_scheme", "mitc4"))
            coordinates = mesh.nodes[connectivity]
            matrices = plate_element_matrices(
                coordinates,
                material,
                plate_method=plate_method,
                shear_scheme=shear_scheme,
            )
            dofs = np.asarray(
                [3 * int(node) + local for node in connectivity for local in range(3)],
                dtype=np.intp,
            )
            local_nodal_force = element_forces[common.id]
            local_force = local_nodal_force.copy()
            pressure = surface_loads[common.id]
            if pressure:
                local_force += q4_consistent_load(coordinates, pressure)
            for local_edge, shear, moment in edge_loads[common.id]:
                local_force += q4_edge_consistent_load(
                    coordinates,
                    local_edge,
                    transverse_shear=shear,
                    moment=moment,
                )
            stiffness[np.ix_(dofs, dofs)] += matrices.total
            force[dofs] += local_force - local_nodal_force

            value = 1.0 / np.sqrt(3.0)
            determinants = [
                kinematic_matrices(coordinates, xi, eta)[0].det_jacobian
                for xi, eta in ((-value, -value), (value, -value), (value, value), (-value, value))
            ]
            normalized_elements.append(
                NativeElement(
                    element_id=common.id,
                    dof_indices=tuple(int(item) for item in dofs),
                    stiffness=matrices.total,
                    force=local_force,
                    min_det_j=float(min(determinants)),
                    metadata={
                        "formulation": f"{plate_method}/{shear_scheme}",
                        "mesh_element_index": index,
                    },
                )
            )
        return NativeSystem(
            stiffness=stiffness,
            force=force,
            elements=tuple(normalized_elements),
            native_model=mesh,
        )

    def native_reference(self, model: ModelInput) -> AdapterRecovery:
        from mindlin_plate import solve_dirichlet

        system = self._build_native_system(model)
        solved = solve_dirichlet(system.stiffness, system.force, self.constraint_map(model))
        energy = float(0.5 * solved.displacement @ system.stiffness @ solved.displacement)
        return AdapterRecovery(
            displacement=solved.displacement,
            reactions=solved.reactions,
            strain_energy=energy,
            element_data=tuple(
                {
                    "element_id": element.element_id,
                    "min_det_j": element.min_det_j,
                }
                for element in system.elements
            ),
            metadata={
                "core_package": self.core_package,
                "free_dof_count": int(solved.free_dofs.size),
            },
        )


__all__ = ["PlateAdapter"]
