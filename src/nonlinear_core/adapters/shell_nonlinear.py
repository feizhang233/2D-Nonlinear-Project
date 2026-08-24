"""P14 adapter for corotational Q4 flat-shell elements."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike, NDArray
from shell_core import build_element_geometry, integrate_edge_traction, integrate_surface_traction

from nonlinear_core.adapters._distributed import edge_targets, surface_element_ids
from nonlinear_core.adapters._mapping import (
    first_connected_elements,
    float_value,
    material_lookup,
    node_index_lookup,
    scaled_components,
)
from nonlinear_core.adapters.base import (
    AdapterIssue,
    AdapterRecovery,
    AdapterState,
    AdapterValidation,
    ElementResponse,
    ModelResponse,
)
from nonlinear_core.contracts import canonical_model_json
from nonlinear_core.elements import evaluate_corotational_flat_shell
from nonlinear_core.model import CoordinateSystem, DofRef, LoadKind, ModelFamily, ModelInput

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class _ShellElement:
    element_id: str
    node_ids: tuple[str, ...]
    coordinates: FloatArray
    dof_indices: tuple[int, ...]
    young: float
    poisson: float
    thickness: float
    shear_correction: float
    alpha_d: float
    differentiation_step: float


@dataclass(frozen=True, slots=True)
class _ShellSystem:
    elements: tuple[_ShellElement, ...]
    reference_load: FloatArray
    element_reference_loads: tuple[FloatArray, ...]


def _vector(value: ArrayLike, *, size: int) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"shell displacement must be finite with shape ({size},)")
    result.setflags(write=False)
    return result


class CorotationalShellAdapter:
    """Assemble large-rigid-rotation/small-local-strain flat shells."""

    family = ModelFamily.SHELL
    adapter_id = "shell-corotational-flat-q4"
    core_package = "shell-core"
    core_version = "1.0.0"

    def validate(self, model: ModelInput) -> AdapterValidation:
        try:
            self._build_system(model)
        except (AssertionError, KeyError, RuntimeError, TypeError, ValueError) as error:
            return AdapterValidation(errors=(AdapterIssue("ADAPTER_MODEL_INVALID", str(error)),))
        return AdapterValidation()

    def initial_state(self, model: ModelInput) -> AdapterState:
        self._require_family(model)
        digest = hashlib.sha256(canonical_model_json(model).encode("utf-8")).hexdigest()
        return AdapterState(
            model_id=model.model_id,
            model_family=model.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id=f"initial:{digest}",
            history={
                "configuration": "reference",
                "kinematics": "corotational-flat-shell",
                "local_strain_scope": "small",
                "shear_formulation": "qlll_assumed_strain",
                "strain_energy": 0.0,
                "membrane_energy": 0.0,
                "bending_energy": 0.0,
                "shear_energy": 0.0,
                "drilling_energy": 0.0,
            },
        )

    def dof_map(self, model: ModelInput) -> tuple[DofRef, ...]:
        self._require_family(model)
        return model.ordered_dof_refs()

    def constraint_map(self, model: ModelInput) -> Mapping[int, float]:
        lookup = {
            (reference.node_id, reference.dof): index
            for index, reference in enumerate(self.dof_map(model))
        }
        return MappingProxyType(
            {
                lookup[(constraint.node_id, constraint.dof)]: float(constraint.value)
                for constraint in model.constraints
            }
        )

    def evaluate(
        self,
        model: ModelInput,
        displacement: ArrayLike,
        *,
        load_factor: float = 1.0,
        committed_state: AdapterState | None = None,
    ) -> ModelResponse:
        system = self._build_system(model)
        size = len(self.dof_map(model))
        vector = _vector(displacement, size=size)
        factor = float(load_factor)
        if not np.isfinite(factor):
            raise ValueError("load_factor must be finite")
        if committed_state is not None:
            self._require_compatible_state(model, committed_state)

        internal = np.zeros(size, dtype=float)
        tangent = np.zeros((size, size), dtype=float)
        membrane_energy = 0.0
        bending_energy = 0.0
        shear_energy = 0.0
        drilling_energy = 0.0
        determinants: list[float] = []
        element_responses: list[ElementResponse] = []
        element_history: dict[str, object] = {}
        for element_index, element in enumerate(system.elements):
            indices = np.asarray(element.dof_indices, dtype=np.intp)
            response = evaluate_corotational_flat_shell(
                element.coordinates,
                vector[indices],
                young=element.young,
                poisson=element.poisson,
                thickness=element.thickness,
                shear_correction=element.shear_correction,
                alpha_d=element.alpha_d,
                differentiation_step=element.differentiation_step,
            )
            internal[indices] += response.internal_force
            tangent[np.ix_(indices, indices)] += response.tangent
            membrane_energy += response.membrane_energy
            bending_energy += response.bending_energy
            shear_energy += response.shear_energy
            drilling_energy += response.drilling_energy
            determinants.append(response.min_det_j)
            element_history[element.element_id] = {
                "membrane_energy": response.membrane_energy,
                "bending_energy": response.bending_energy,
                "shear_energy": response.shear_energy,
                "drilling_energy": response.drilling_energy,
                "alpha_d": response.alpha_d,
            }
            metadata = {
                "formulation": "Q4-corotational-flat-shell-RM",
                "kinematic_scope": "large-rigid-rotation-small-local-strain",
                "shear_formulation": "qlll_assumed_strain",
                "drilling_formulation": "continuum_consistent",
                "alpha_d": response.alpha_d,
                "differentiation_step": response.differentiation_step,
                "node_ids": list(element.node_ids),
                "current_basis": response.current_basis.tolist(),
                "rigid_rotation_vector": response.rigid_rotation_vector.tolist(),
                "local_deformation_norm": float(np.linalg.norm(response.local_deformation)),
                "gauss_points": list(response.gauss_points),
                "membrane_energy": response.membrane_energy,
                "bending_energy": response.bending_energy,
                "shear_energy": response.shear_energy,
                "drilling_energy": response.drilling_energy,
            }
            element_responses.append(
                ElementResponse(
                    element_id=element.element_id,
                    dof_indices=element.dof_indices,
                    internal_force=response.internal_force,
                    tangent=response.tangent,
                    external_force=factor * system.element_reference_loads[element_index],
                    energy=response.strain_energy,
                    min_det_j=response.min_det_j,
                    metadata=metadata,
                )
            )

        total_energy = membrane_energy + bending_energy + shear_energy + drilling_energy
        external = factor * system.reference_load
        digest = hashlib.sha256(
            np.concatenate((vector, np.asarray([factor]))).tobytes()
        ).hexdigest()
        trial_state = AdapterState(
            model_id=model.model_id,
            model_family=model.model_family,
            adapter_id=self.adapter_id,
            core_package=self.core_package,
            core_version=self.core_version,
            state_id=f"trial:{digest}",
            history={
                "configuration": "current-corotational-frame",
                "kinematics": "corotational-flat-shell",
                "local_strain_scope": "small",
                "shear_formulation": "qlll_assumed_strain",
                "load_factor": factor,
                "strain_energy": total_energy,
                "membrane_energy": membrane_energy,
                "bending_energy": bending_energy,
                "shear_energy": shear_energy,
                "drilling_energy": drilling_energy,
                "elements": element_history,
            },
        )
        return ModelResponse(
            internal_force=internal,
            tangent=tangent,
            external_force=external,
            external_tangent=None,
            trial_state=trial_state,
            elements=tuple(element_responses),
            strain_energy=float(total_energy),
            min_det_j=min(determinants),
            metadata={
                "formulation": "Q4-corotational-flat-shell-RM",
                "kinematic_scope": "large-rigid-rotation-small-local-strain",
                "shear_formulation": "qlll_assumed_strain",
                "drilling_formulation": "continuum_consistent",
                "reference_load_type": "fixed-global nodal/consistent-surface/consistent-edge",
                "dof_order": [reference.dof.value for reference in self.dof_map(model)],
                "membrane_energy": membrane_energy,
                "bending_energy": bending_energy,
                "shear_energy": shear_energy,
                "drilling_energy": drilling_energy,
            },
        )

    def recover(
        self,
        model: ModelInput,
        displacement: ArrayLike,
        *,
        load_factor: float = 1.0,
        committed_state: AdapterState | None = None,
    ) -> AdapterRecovery:
        response = self.evaluate(
            model,
            displacement,
            load_factor=load_factor,
            committed_state=committed_state,
        )
        return AdapterRecovery(
            displacement=displacement,
            reactions=response.internal_force - response.external_force,
            strain_energy=response.strain_energy,
            element_data=tuple(
                {
                    "element_id": item.element_id,
                    "energy": item.energy,
                    "min_det_j": item.min_det_j,
                    **dict(item.metadata),
                }
                for item in response.elements
            ),
            metadata={
                "adapter_id": self.adapter_id,
                "load_factor": float(load_factor),
                "kinematics": "corotational-flat-shell",
                "kinematic_scope": "large-rigid-rotation-small-local-strain",
                "raw_result_location": "gauss_point",
                "raw_resultants": ["N", "M", "Q"],
                "nodal_averaging": "not-applied",
            },
        )

    def _build_system(self, model: ModelInput) -> _ShellSystem:
        self._require_family(model)
        expected_units = {"length": "m", "force": "N", "stress": "Pa", "angle": "rad"}
        observed_units = {
            "length": model.units.length,
            "force": model.units.force,
            "stress": model.units.stress,
            "angle": model.units.angle,
        }
        if observed_units != expected_units:
            raise ValueError(f"P14 shell adapter requires SI labels {expected_units}")

        node_indices = node_index_lookup(model)
        materials = material_lookup(model)
        elements: list[_ShellElement] = []
        for common in model.elements:
            formulation = common.formulation.strip().lower().replace("_", "-")
            if len(common.node_ids) != 4 or not all(
                token in formulation for token in ("q4", "corotational", "flat-shell")
            ):
                raise ValueError(
                    f"shell element {common.id!r} must use four-node Q4-corotational-flat-shell-RM"
                )
            material = materials[common.material_id]
            material_name = material.model.strip().lower().replace("_", "-")
            if material_name not in {"linear-elastic", "linear-elastic-isotropic"}:
                raise ValueError(f"shell material {material.id!r} must be linear-elastic-isotropic")
            coordinates = []
            for node_id in common.node_ids:
                node_coordinates = list(model.nodes[node_indices[node_id]].coordinates)
                if len(node_coordinates) == 2:
                    node_coordinates.append(0.0)
                coordinates.append(node_coordinates)
            dofs = tuple(
                6 * node_indices[node_id] + local
                for node_id in common.node_ids
                for local in range(6)
            )
            element = _ShellElement(
                element_id=common.id,
                node_ids=common.node_ids,
                coordinates=np.asarray(coordinates, dtype=float),
                dof_indices=dofs,
                young=float_value(material.parameters, "young", "young_modulus", "E"),
                poisson=float_value(material.parameters, "poisson", "poisson_ratio", "nu"),
                thickness=float_value(common.properties, "thickness"),
                shear_correction=float_value(
                    common.properties,
                    "shear_correction",
                    "shear_correction_factor",
                    default=5.0 / 6.0,
                ),
                alpha_d=float_value(common.properties, "alpha_d", default=1.0e-4),
                differentiation_step=float_value(
                    common.properties,
                    "differentiation_step",
                    default=2.0e-5,
                ),
            )
            evaluate_corotational_flat_shell(
                element.coordinates,
                np.zeros(24),
                young=element.young,
                poisson=element.poisson,
                thickness=element.thickness,
                shear_correction=element.shear_correction,
                alpha_d=element.alpha_d,
                differentiation_step=element.differentiation_step,
            )
            elements.append(element)

        size = 6 * len(model.nodes)
        reference_load = np.zeros(size, dtype=float)
        element_loads = [np.zeros(24, dtype=float) for _ in elements]
        owner_by_node = first_connected_elements(model)
        element_index = {element.element_id: index for index, element in enumerate(elements)}
        component_order = ("UX", "UY", "UZ", "RX", "RY", "RZ")
        for load in model.loads:
            if load.coordinate_system is not CoordinateSystem.GLOBAL:
                raise ValueError(f"P14 shell load {load.id!r} must use global coordinates")
            components = scaled_components(load)
            if load.kind is LoadKind.NODAL:
                assert load.node_id is not None
                node_index = node_indices[load.node_id]
                nodal_force = np.asarray(
                    [components.get(component, 0.0) for component in component_order],
                    dtype=float,
                )
                reference_load[6 * node_index : 6 * node_index + 6] += nodal_force
                owner_index = element_index[owner_by_node[load.node_id]]
                owner = elements[owner_index]
                local_node = owner.node_ids.index(load.node_id)
                element_loads[owner_index][6 * local_node : 6 * local_node + 6] += nodal_force
                continue
            traction = (
                components.get("UX", 0.0),
                components.get("UY", 0.0),
                components.get("UZ", 0.0),
            )
            if load.kind is LoadKind.SURFACE:
                for element_id in surface_element_ids(load, set(element_index)):
                    index = element_index[element_id]
                    owner = elements[index]
                    geometry = build_element_geometry(owner.coordinates.tolist())
                    local_force = np.asarray(
                        integrate_surface_traction(geometry, traction), dtype=float
                    )
                    reference_load[np.asarray(owner.dof_indices, dtype=np.intp)] += local_force
                    element_loads[index] += local_force
                continue
            if load.kind is LoadKind.EDGE:
                for target in edge_targets(load, set(element_index)):
                    index = element_index[target.element_id]
                    owner = elements[index]
                    geometry = build_element_geometry(owner.coordinates.tolist())
                    local_force = np.asarray(
                        integrate_edge_traction(geometry, target.local_edge + 1, traction),
                        dtype=float,
                    )
                    reference_load[np.asarray(owner.dof_indices, dtype=np.intp)] += local_force
                    element_loads[index] += local_force
                continue
            raise ValueError(
                f"P14 shell adapter does not support {load.kind.value!r} load {load.id!r}"
            )

        reference_load.setflags(write=False)
        for element_load in element_loads:
            element_load.setflags(write=False)
        return _ShellSystem(
            elements=tuple(elements),
            reference_load=reference_load,
            element_reference_loads=tuple(element_loads),
        )

    def _require_family(self, model: ModelInput) -> None:
        if not isinstance(model, ModelInput):
            raise TypeError("model must be a validated nonlinear_core.ModelInput")
        if model.model_family is not ModelFamily.SHELL:
            raise ValueError(
                f"{self.adapter_id} requires family 'shell'; got {model.model_family.value!r}"
            )

    def _require_compatible_state(self, model: ModelInput, state: AdapterState) -> None:
        if state.model_id != model.model_id or state.adapter_id != self.adapter_id:
            raise ValueError("committed_state belongs to a different model or adapter")


__all__ = ["CorotationalShellAdapter"]
