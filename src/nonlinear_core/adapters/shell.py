"""Adapter for the installed ``shell-core`` 1.0 public API."""

from __future__ import annotations

import numpy as np

from nonlinear_core.adapters._mapping import (
    first_connected_elements,
    float_value,
    material_lookup,
    scaled_components,
)
from nonlinear_core.adapters.base import (
    AdapterRecovery,
    LinearCoreAdapter,
    NativeElement,
    NativeSystem,
)
from nonlinear_core.model import CoordinateSystem, LoadKind, ModelFamily, ModelInput


class ShellAdapter(LinearCoreAdapter):
    family = ModelFamily.SHELL
    adapter_id = "shell-core-linear"
    core_package = "shell-core"
    core_version = "1.0.0"

    def _native_document(self, model: ModelInput) -> dict[str, object]:
        self._require_family(model)
        expected_units = {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"}
        observed_units = {
            "length": model.units.length,
            "force": model.units.force,
            "stress": model.units.stress,
            "angle": model.units.angle,
        }
        if observed_units != expected_units:
            raise ValueError(
                f"shell-core 1.0 requires SI unit labels {expected_units}; got {observed_units}"
            )
        materials = material_lookup(model)
        native_materials = []
        for material in model.materials:
            native_materials.append(
                {
                    "id": material.id,
                    "type": "linear_elastic_isotropic",
                    "young_modulus": float_value(
                        material.parameters, "young", "young_modulus", "E"
                    ),
                    "poisson_ratio": float_value(
                        material.parameters, "poisson", "poisson_ratio", "nu"
                    ),
                }
            )

        sections = []
        elements = []
        for element in model.elements:
            if len(element.node_ids) != 4:
                raise ValueError(f"shell element {element.id!r} requires exactly 4 nodes")
            if "q4" not in element.formulation.strip().lower() and "shell" not in (
                element.formulation.strip().lower()
            ):
                raise ValueError(
                    f"unsupported shell formulation {element.formulation!r}; use Q4 shell"
                )
            material = materials[element.material_id]
            section_id = f"P2_SECTION_{element.id}"
            sections.append(
                {
                    "id": section_id,
                    "type": "homogeneous_constant_thickness",
                    "material_id": material.id,
                    "thickness": float_value(element.properties, "thickness"),
                    "shear_correction_factor": float_value(
                        element.properties,
                        "shear_correction",
                        "shear_correction_factor",
                        default=5.0 / 6.0,
                    ),
                }
            )
            elements.append(
                {
                    "id": element.id,
                    "type": "Q4_FLAT_SHELL_RM",
                    "node_ids": list(element.node_ids),
                    "section_id": section_id,
                }
            )

        loads = []
        for load in model.loads:
            if load.coordinate_system is not CoordinateSystem.GLOBAL:
                raise ValueError(f"shell load {load.id!r} must use global coordinates")
            components = scaled_components(load)
            force = [
                components.get("UX", 0.0),
                components.get("UY", 0.0),
                components.get("UZ", 0.0),
            ]
            if load.kind is LoadKind.NODAL:
                assert load.node_id is not None
                loads.append(
                    {
                        "id": load.id,
                        "type": "nodal_load",
                        "node_id": load.node_id,
                        "force_global": force,
                        "moment_global": [
                            components.get("RX", 0.0),
                            components.get("RY", 0.0),
                            components.get("RZ", 0.0),
                        ],
                    }
                )
            elif load.kind is LoadKind.SURFACE:
                assert load.element_id is not None
                self._reject_moment_components(load.id, components)
                loads.append(
                    {
                        "id": load.id,
                        "type": "surface_traction",
                        "element_ids": [load.element_id],
                        "traction_global": force,
                    }
                )
            elif load.kind is LoadKind.EDGE:
                assert load.element_id is not None
                self._reject_moment_components(load.id, components)
                local_edge = load.extensions.get("local_edge")
                if isinstance(local_edge, bool) or not isinstance(local_edge, int):
                    raise ValueError(
                        f"shell edge load {load.id!r} requires integer extensions.local_edge"
                    )
                loads.append(
                    {
                        "id": load.id,
                        "type": "edge_traction",
                        "element_id": load.element_id,
                        "local_edge": local_edge,
                        "traction_global": force,
                    }
                )
            elif load.kind is LoadKind.BODY:
                self._reject_moment_components(load.id, components)
                loads.append(
                    {
                        "id": load.id,
                        "type": "body_force",
                        "element_ids": [element.id for element in model.elements],
                        "force_density_global": force,
                    }
                )
            else:
                raise ValueError(
                    f"shell adapter does not support {load.kind.value!r} load {load.id!r}"
                )

        nodes = []
        for node in model.nodes:
            coordinates = list(node.coordinates)
            if len(coordinates) == 2:
                coordinates.append(0.0)
            nodes.append({"id": node.id, "coordinates": coordinates})

        return {
            "document_type": "model_input",
            "schema_version": "1.0.0",
            "model_id": model.model_id,
            "title": model.name,
            "units": {
                "system": "SI",
                "length": "m",
                "angle": "rad",
                "force": "N",
                "moment": "N*m",
                "bending_resultant": "N",
                "stress": "Pa",
                "line_load": "N/m",
                "surface_load": "N/m^2",
                "body_force": "N/m^3",
                "energy": "J",
            },
            "nodes": nodes,
            "materials": native_materials,
            "sections": sections,
            "elements": elements,
            "load_case": {"id": "P2_LINEAR_REFERENCE", "loads": loads},
            "constraints": [
                {
                    "id": constraint.id,
                    "node_id": constraint.node_id,
                    "dof": constraint.dof.value,
                    "value": float(constraint.value),
                }
                for constraint in model.constraints
            ],
            "analysis_options": {
                "run_purpose": "production",
                "kinematics": "linear_small_rotation",
                "element_formulation": "q4_reissner_mindlin_flat_shell",
                "shear_formulation": "qlll_assumed_strain",
                "integration_rule": "gauss_2x2",
                "drilling": {
                    "formulation": "continuum_consistent",
                    "alpha_d": 1.0e-4,
                },
                "geometry_policy": "strict_flat_q4_v1",
                "solver": {
                    "method": "symmetric_direct",
                    "scaling": "characteristic_length",
                    "relative_backward_error_tolerance": 1.0e-10,
                    "condition_warning_threshold": 1.0e12,
                },
                "precision": "float64",
            },
        }

    @staticmethod
    def _reject_moment_components(load_id: str, components: dict[str, float]) -> None:
        if any(components.get(name, 0.0) != 0.0 for name in ("RX", "RY", "RZ")):
            raise ValueError(f"distributed shell load {load_id!r} cannot contain moments")

    def _build_native_system(self, model: ModelInput) -> NativeSystem:
        from shell_core import assemble_system, validate_model

        validation = validate_model(self._native_document(model))
        if not validation.solvable or validation.validated_model is None:
            details = "; ".join(f"{item.code}: {item.message}" for item in validation.errors)
            raise ValueError(f"shell-core validation failed: {details}")
        native_model = validation.validated_model
        assembled = assemble_system(native_model)
        stiffness = np.asarray(assembled.stiffness.to_dense(), dtype=float)
        force = np.asarray(assembled.applied_load, dtype=float)

        connected_owner = first_connected_elements(model)
        owned_nodal: dict[str, np.ndarray] = {
            element.id: np.zeros(24, dtype=float) for element in model.elements
        }
        for load in model.loads:
            if load.kind is not LoadKind.NODAL:
                continue
            assert load.node_id is not None
            owner_id = connected_owner[load.node_id]
            owner = next(item for item in model.elements if item.id == owner_id)
            local_node = owner.node_ids.index(load.node_id)
            components = scaled_components(load)
            owned_nodal[owner_id][6 * local_node : 6 * local_node + 6] += (
                components.get("UX", 0.0),
                components.get("UY", 0.0),
                components.get("UZ", 0.0),
                components.get("RX", 0.0),
                components.get("RY", 0.0),
                components.get("RZ", 0.0),
            )

        normalized_elements = []
        for common, contribution in zip(model.elements, assembled.elements, strict=True):
            determinants = [point.jacobian.det_j for point in contribution.geometry.gauss_points]
            normalized_elements.append(
                NativeElement(
                    element_id=common.id,
                    dof_indices=contribution.dof_indices,
                    stiffness=np.asarray(contribution.operator.k_global, dtype=float),
                    force=np.asarray(contribution.load_global, dtype=float)
                    + owned_nodal[common.id],
                    min_det_j=float(min(determinants)),
                    metadata={
                        "formulation": "Q4_FLAT_SHELL_RM",
                        "shear_formulation": contribution.operator.shear_formulation,
                        "drilling_formulation": contribution.operator.drilling_formulation,
                    },
                )
            )
        return NativeSystem(
            stiffness=stiffness,
            force=force,
            elements=tuple(normalized_elements),
            native_model=native_model,
            native_context={"assembled": assembled},
        )

    def native_reference(self, model: ModelInput) -> AdapterRecovery:
        from shell_core import solve_linear_static

        system = self._build_native_system(model)
        solved = solve_linear_static(system.native_model)
        if solved.status != "succeeded":
            details = "; ".join(f"{item.code}: {item.message}" for item in solved.errors)
            raise RuntimeError(f"shell-core solve failed: {details}")
        assert solved.displacement_vector is not None
        assert solved.residual_vector is not None
        assert solved.strain_energy is not None
        return AdapterRecovery(
            displacement=solved.displacement_vector,
            reactions=solved.residual_vector,
            strain_energy=float(solved.strain_energy),
            element_data=tuple(
                {
                    "element_id": element.element_id,
                    "min_det_j": element.min_det_j,
                }
                for element in system.elements
            ),
            metadata={
                "core_package": self.core_package,
                "diagnostic_count": len(solved.diagnostics),
            },
        )


__all__ = ["ShellAdapter"]
