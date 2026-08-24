"""P12 adapter for plane-strain Total Lagrangian Q4 continuum elements."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike, NDArray

from nonlinear_core.adapters._distributed import edge_targets
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
from nonlinear_core.constants import PACKAGE_VERSION
from nonlinear_core.contracts import canonical_model_json
from nonlinear_core.elements import (
    TotalLagrangianQ4Error,
    evaluate_total_lagrangian_q4,
)
from nonlinear_core.model import CoordinateSystem, DofRef, LoadKind, ModelFamily, ModelInput

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class _ContinuumElement:
    element_id: str
    node_ids: tuple[str, ...]
    coordinates: FloatArray
    dof_indices: tuple[int, ...]
    young: float
    poisson: float
    thickness: float


@dataclass(frozen=True, slots=True)
class _ContinuumSystem:
    elements: tuple[_ContinuumElement, ...]
    reference_load: FloatArray
    element_reference_loads: tuple[FloatArray, ...]


def _vector(value: ArrayLike, *, size: int) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"continuum displacement must be finite with shape ({size},)")
    result.setflags(write=False)
    return result


class TotalLagrangianContinuumAdapter:
    """Assemble P12 objective hyperelastic Q4 responses for the common solver."""

    family = ModelFamily.CONTINUUM
    adapter_id = "continuum-total-lagrangian-q4"
    core_package = "nonlinear-core-continuum-tl-q4"
    core_version = PACKAGE_VERSION

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
                "kinematics": "total-lagrangian",
                "material": "saint-venant-kirchhoff",
                "plane_mode": "plane_strain",
                "strain_energy": 0.0,
                "min_det_f": 1.0,
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
        energy = 0.0
        det_j_values: list[float] = []
        det_f_values: list[float] = []
        element_responses: list[ElementResponse] = []
        element_history: dict[str, object] = {}
        for element_index, element in enumerate(system.elements):
            indices = np.asarray(element.dof_indices, dtype=np.intp)
            local_displacement = vector[indices]
            failure_metadata: dict[str, object] | None = None
            try:
                response = evaluate_total_lagrangian_q4(
                    element.coordinates,
                    local_displacement,
                    young=element.young,
                    poisson=element.poisson,
                    thickness=element.thickness,
                    element_id=element.element_id,
                )
            except TotalLagrangianQ4Error as error:
                if error.code == "CONTINUUM_REFERENCE_MAPPING_INVALID":
                    raise
                local_internal = np.zeros(8, dtype=float)
                local_tangent = np.zeros((8, 8), dtype=float)
                local_energy = 0.0
                min_det_j = 0.0 if error.min_det_j is None else float(error.min_det_j)
                min_det_f = (
                    0.0
                    if error.min_det_f is None or not np.isfinite(error.min_det_f)
                    else float(error.min_det_f)
                )
                gauss_points: tuple[dict[str, object], ...] = ()
                failure_metadata = {
                    "failure_code": error.code,
                    "failure_message": str(error),
                }
                material_tangent_norm = 0.0
                geometric_tangent_norm = 0.0
            else:
                local_internal = response.internal_force
                local_tangent = response.tangent
                local_energy = response.strain_energy
                min_det_j = response.min_det_j
                min_det_f = response.min_det_f
                gauss_points = response.gauss_points
                material_tangent_norm = float(np.linalg.norm(response.material_tangent))
                geometric_tangent_norm = float(np.linalg.norm(response.geometric_tangent))

            internal[indices] += local_internal
            tangent[np.ix_(indices, indices)] += local_tangent
            energy += local_energy
            det_j_values.append(min_det_j)
            det_f_values.append(min_det_f)
            element_history[element.element_id] = {
                "min_det_f": min_det_f,
                "strain_energy": local_energy,
            }
            metadata = {
                "formulation": "Q4-total-lagrangian",
                "material": "saint-venant-kirchhoff",
                "plane_mode": "plane_strain",
                "integration": "2x2-gauss",
                "node_ids": list(element.node_ids),
                "gauss_points": list(gauss_points),
                "material_tangent_norm": material_tangent_norm,
                "geometric_tangent_norm": geometric_tangent_norm,
            }
            if failure_metadata is not None:
                metadata.update(failure_metadata)
            element_responses.append(
                ElementResponse(
                    element_id=element.element_id,
                    dof_indices=element.dof_indices,
                    internal_force=local_internal,
                    tangent=local_tangent,
                    external_force=factor * system.element_reference_loads[element_index],
                    energy=local_energy,
                    min_det_j=min_det_j,
                    min_det_f=min_det_f,
                    metadata=metadata,
                )
            )

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
                "configuration": "current",
                "kinematics": "total-lagrangian",
                "material": "saint-venant-kirchhoff",
                "plane_mode": "plane_strain",
                "load_factor": factor,
                "strain_energy": energy,
                "min_det_f": min(det_f_values),
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
            strain_energy=float(energy),
            min_det_j=min(det_j_values),
            min_det_f=min(det_f_values),
            metadata={
                "formulation": "Q4-total-lagrangian",
                "material": "saint-venant-kirchhoff",
                "plane_mode": "plane_strain",
                "reference_load_type": "fixed-global nodal/consistent-edge",
                "dof_order": [reference.dof.value for reference in self.dof_map(model)],
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
                    "min_det_f": item.min_det_f,
                    **dict(item.metadata),
                }
                for item in response.elements
            ),
            metadata={
                "adapter_id": self.adapter_id,
                "load_factor": float(load_factor),
                "configuration": "current",
                "kinematics": "total-lagrangian",
                "stress_measures": ["second_piola", "cauchy"],
                "strain_measure": "green_lagrange",
                "raw_result_location": "gauss_point",
            },
        )

    def _build_system(self, model: ModelInput) -> _ContinuumSystem:
        self._require_family(model)
        if (
            model.units.length != "m"
            or model.units.force != "N"
            or model.units.stress != "Pa"
            or model.units.angle != "rad"
        ):
            raise ValueError("P12 continuum adapter requires SI labels m/N/Pa/rad")
        node_indices = node_index_lookup(model)
        materials = material_lookup(model)
        elements: list[_ContinuumElement] = []
        for common in model.elements:
            formulation = common.formulation.strip().lower().replace("_", "-")
            if len(common.node_ids) != 4 or not (
                "q4" in formulation and "total-lagrangian" in formulation
            ):
                raise ValueError(
                    f"continuum element {common.id!r} must use four-node Q4-total-lagrangian"
                )
            material = materials[common.material_id]
            material_name = material.model.strip().lower().replace("_", "-")
            if material_name not in {
                "saint-venant-kirchhoff",
                "st-venant-kirchhoff",
                "svk",
            }:
                raise ValueError(
                    f"continuum material {material.id!r} must be Saint-Venant--Kirchhoff"
                )
            plane_mode = str(material.parameters.get("plane_mode", ""))
            if plane_mode != "plane_strain":
                raise ValueError(
                    f"continuum material {material.id!r} requires plane_mode='plane_strain'"
                )
            coordinates = np.asarray(
                [model.nodes[node_indices[node_id]].coordinates[:2] for node_id in common.node_ids],
                dtype=float,
            )
            dofs = tuple(
                dof
                for node_id in common.node_ids
                for dof in (2 * node_indices[node_id], 2 * node_indices[node_id] + 1)
            )
            element = _ContinuumElement(
                element_id=common.id,
                node_ids=common.node_ids,
                coordinates=coordinates,
                dof_indices=dofs,
                young=float_value(material.parameters, "young", "young_modulus", "E"),
                poisson=float_value(material.parameters, "poisson", "poisson_ratio", "nu"),
                thickness=float_value(common.properties, "thickness", default=1.0),
            )
            evaluate_total_lagrangian_q4(
                element.coordinates,
                np.zeros(8),
                young=element.young,
                poisson=element.poisson,
                thickness=element.thickness,
                element_id=element.element_id,
            )
            elements.append(element)

        size = 2 * len(model.nodes)
        reference_load = np.zeros(size, dtype=float)
        element_loads = [np.zeros(8, dtype=float) for _ in elements]
        owner_by_node = first_connected_elements(model)
        element_index = {element.element_id: index for index, element in enumerate(elements)}
        local_edges = ((0, 1), (1, 2), (2, 3), (3, 0))
        for load in model.loads:
            if load.coordinate_system is not CoordinateSystem.GLOBAL:
                raise ValueError(f"P12 continuum load {load.id!r} must use global coordinates")
            components = scaled_components(load)
            if load.kind is LoadKind.NODAL:
                assert load.node_id is not None
                node_index = node_indices[load.node_id]
                nodal_force = np.asarray(
                    [components.get("UX", 0.0), components.get("UY", 0.0)],
                    dtype=float,
                )
                reference_load[2 * node_index : 2 * node_index + 2] += nodal_force
                owner_index = element_index[owner_by_node[load.node_id]]
                owner = elements[owner_index]
                local_node = owner.node_ids.index(load.node_id)
                element_loads[owner_index][2 * local_node : 2 * local_node + 2] += nodal_force
                continue
            if load.kind is not LoadKind.EDGE:
                raise ValueError(
                    f"P12 continuum adapter does not support {load.kind.value!r} load {load.id!r}"
                )
            line_load = np.asarray(
                [components.get("UX", 0.0), components.get("UY", 0.0)], dtype=float
            )
            for target in edge_targets(load, set(element_index)):
                index = element_index[target.element_id]
                owner = elements[index]
                left, right = local_edges[target.local_edge]
                edge_length = float(
                    np.linalg.norm(owner.coordinates[right] - owner.coordinates[left])
                )
                edge_force = 0.5 * edge_length * line_load
                local_force = np.zeros(8, dtype=float)
                local_force[2 * left : 2 * left + 2] += edge_force
                local_force[2 * right : 2 * right + 2] += edge_force
                reference_load[np.asarray(owner.dof_indices, dtype=np.intp)] += local_force
                element_loads[index] += local_force
        reference_load.setflags(write=False)
        for element_load in element_loads:
            element_load.setflags(write=False)
        return _ContinuumSystem(
            elements=tuple(elements),
            reference_load=reference_load,
            element_reference_loads=tuple(element_loads),
        )

    def _require_family(self, model: ModelInput) -> None:
        if not isinstance(model, ModelInput):
            raise TypeError("model must be a validated nonlinear_core.ModelInput")
        if model.model_family is not ModelFamily.CONTINUUM:
            raise ValueError(
                f"{self.adapter_id} requires family 'continuum'; got {model.model_family.value!r}"
            )

    def _require_compatible_state(self, model: ModelInput, state: AdapterState) -> None:
        if state.model_id != model.model_id or state.adapter_id != self.adapter_id:
            raise ValueError("committed_state belongs to a different model or adapter")


__all__ = ["TotalLagrangianContinuumAdapter"]
