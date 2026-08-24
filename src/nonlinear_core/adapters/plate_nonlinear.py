"""P13 adapter for Q4 von Karman plates with MITC4 transverse shear."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike, NDArray

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
from nonlinear_core.elements import evaluate_von_karman_mitc4
from nonlinear_core.model import CoordinateSystem, DofRef, LoadKind, ModelFamily, ModelInput

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class _PlateElement:
    element_id: str
    node_ids: tuple[str, ...]
    coordinates: FloatArray
    dof_indices: tuple[int, ...]
    young: float
    poisson: float
    thickness: float
    shear_correction: float


@dataclass(frozen=True, slots=True)
class _PlateSystem:
    elements: tuple[_PlateElement, ...]
    reference_load: FloatArray
    element_reference_loads: tuple[FloatArray, ...]


def _vector(value: ArrayLike, *, size: int) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"plate displacement must be finite with shape ({size},)")
    result.setflags(write=False)
    return result


def _embed_plate_vector(values: ArrayLike) -> FloatArray:
    source = np.asarray(values, dtype=float)
    if source.shape != (12,):
        raise ValueError("plate-core vector must have shape (12,)")
    target = np.zeros(20, dtype=float)
    for node in range(4):
        target[5 * node + 2 : 5 * node + 5] = source[3 * node : 3 * node + 3]
    return target


class VonKarmanPlateAdapter:
    """Assemble moderate-rotation plate responses for the common nonlinear solver."""

    family = ModelFamily.PLATE
    adapter_id = "plate-von-karman-mitc4"
    core_package = "mindlin-plate-core"
    core_version = "0.3.0"

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
                "configuration": "reference-planform",
                "kinematics": "von-karman",
                "plate_theory": "reissner-mindlin",
                "shear_scheme": "mitc4",
                "strain_energy": 0.0,
                "membrane_energy": 0.0,
                "bending_energy": 0.0,
                "shear_energy": 0.0,
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
        determinants: list[float] = []
        element_responses: list[ElementResponse] = []
        element_history: dict[str, object] = {}
        for element_index, element in enumerate(system.elements):
            indices = np.asarray(element.dof_indices, dtype=np.intp)
            response = evaluate_von_karman_mitc4(
                element.coordinates,
                vector[indices],
                young=element.young,
                poisson=element.poisson,
                thickness=element.thickness,
                shear_correction=element.shear_correction,
            )
            internal[indices] += response.internal_force
            tangent[np.ix_(indices, indices)] += response.tangent
            membrane_energy += response.membrane_energy
            bending_energy += response.bending_energy
            shear_energy += response.shear_energy
            determinants.append(response.min_det_j)
            element_history[element.element_id] = {
                "membrane_energy": response.membrane_energy,
                "bending_energy": response.bending_energy,
                "shear_energy": response.shear_energy,
            }
            metadata = {
                "formulation": "Q4-von-karman-MITC4",
                "kinematic_scope": "moderate-rotation-small-strain",
                "plate_theory": "reissner-mindlin",
                "shear_scheme": "mitc4",
                "integration": "2x2-gauss",
                "node_ids": list(element.node_ids),
                "gauss_points": list(response.gauss_points),
                "membrane_energy": response.membrane_energy,
                "bending_energy": response.bending_energy,
                "shear_energy": response.shear_energy,
                "membrane_material_tangent_norm": float(
                    np.linalg.norm(response.membrane_material_tangent)
                ),
                "membrane_geometric_tangent_norm": float(
                    np.linalg.norm(response.membrane_geometric_tangent)
                ),
                "bending_tangent_norm": float(np.linalg.norm(response.bending_tangent)),
                "shear_tangent_norm": float(np.linalg.norm(response.shear_tangent)),
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

        total_energy = membrane_energy + bending_energy + shear_energy
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
                "configuration": "reference-planform",
                "kinematics": "von-karman",
                "plate_theory": "reissner-mindlin",
                "shear_scheme": "mitc4",
                "load_factor": factor,
                "strain_energy": total_energy,
                "membrane_energy": membrane_energy,
                "bending_energy": bending_energy,
                "shear_energy": shear_energy,
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
                "formulation": "Q4-von-karman-MITC4",
                "kinematic_scope": "moderate-rotation-small-strain",
                "plate_theory": "reissner-mindlin",
                "shear_scheme": "mitc4",
                "reference_load_type": "fixed-global nodal/consistent-surface/consistent-edge",
                "dof_order": [reference.dof.value for reference in self.dof_map(model)],
                "membrane_energy": membrane_energy,
                "bending_energy": bending_energy,
                "shear_energy": shear_energy,
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
                "kinematics": "von-karman",
                "kinematic_scope": "moderate-rotation-small-strain",
                "plate_theory": "reissner-mindlin",
                "shear_scheme": "mitc4",
                "raw_result_location": "gauss_point",
                "nodal_averaging": "not-applied",
            },
        )

    def _build_system(self, model: ModelInput) -> _PlateSystem:
        self._require_family(model)
        from mindlin_plate import q4_consistent_load, q4_edge_consistent_load

        node_indices = node_index_lookup(model)
        materials = material_lookup(model)
        elements: list[_PlateElement] = []
        for common in model.elements:
            formulation = common.formulation.strip().lower().replace("_", "-")
            if len(common.node_ids) != 4 or not all(
                token in formulation for token in ("q4", "von-karman", "mitc4")
            ):
                raise ValueError(
                    f"plate element {common.id!r} must use four-node Q4-von-karman-MITC4"
                )
            plate_method = str(common.properties.get("plate_method", "M")).strip().upper()
            shear_scheme = str(common.properties.get("shear_scheme", "mitc4")).strip().lower()
            if plate_method != "M" or shear_scheme != "mitc4":
                raise ValueError(
                    f"plate element {common.id!r} requires plate_method='M' and "
                    "shear_scheme='mitc4'"
                )
            material = materials[common.material_id]
            material_name = material.model.strip().lower().replace("_", "-")
            if material_name not in {"linear-elastic", "isotropic-linear-elastic"}:
                raise ValueError(f"plate material {material.id!r} must be isotropic linear-elastic")
            coordinates = np.asarray(
                [model.nodes[node_indices[node_id]].coordinates[:2] for node_id in common.node_ids],
                dtype=float,
            )
            dofs = tuple(
                5 * node_indices[node_id] + local
                for node_id in common.node_ids
                for local in range(5)
            )
            element = _PlateElement(
                element_id=common.id,
                node_ids=common.node_ids,
                coordinates=coordinates,
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
            )
            evaluate_von_karman_mitc4(
                element.coordinates,
                np.zeros(20),
                young=element.young,
                poisson=element.poisson,
                thickness=element.thickness,
                shear_correction=element.shear_correction,
            )
            elements.append(element)

        size = 5 * len(model.nodes)
        reference_load = np.zeros(size, dtype=float)
        element_loads = [np.zeros(20, dtype=float) for _ in elements]
        owner_by_node = first_connected_elements(model)
        element_index = {element.element_id: index for index, element in enumerate(elements)}
        component_order = ("UX", "UY", "UZ", "RX", "RY")
        for load in model.loads:
            if load.coordinate_system is not CoordinateSystem.GLOBAL:
                raise ValueError(f"P13 plate load {load.id!r} must use global coordinates")
            components = scaled_components(load)
            if load.kind is LoadKind.NODAL:
                assert load.node_id is not None
                node_index = node_indices[load.node_id]
                nodal_force = np.asarray(
                    [components.get(component, 0.0) for component in component_order],
                    dtype=float,
                )
                reference_load[5 * node_index : 5 * node_index + 5] += nodal_force
                owner_index = element_index[owner_by_node[load.node_id]]
                owner = elements[owner_index]
                local_node = owner.node_ids.index(load.node_id)
                element_loads[owner_index][5 * local_node : 5 * local_node + 5] += nodal_force
                continue
            if load.kind is LoadKind.SURFACE:
                for element_id in surface_element_ids(load, set(element_index)):
                    index = element_index[element_id]
                    local = _embed_plate_vector(
                        q4_consistent_load(elements[index].coordinates, components.get("UZ", 0.0))
                    )
                    reference_load[np.asarray(elements[index].dof_indices, dtype=np.intp)] += local
                    element_loads[index] += local
                continue
            if load.kind is LoadKind.EDGE:
                for target in edge_targets(load, set(element_index)):
                    index = element_index[target.element_id]
                    local = _embed_plate_vector(
                        q4_edge_consistent_load(
                            elements[index].coordinates,
                            target.local_edge,
                            transverse_shear=components.get("UZ", 0.0),
                            moment=(
                                components.get("RX", 0.0),
                                components.get("RY", 0.0),
                            ),
                        )
                    )
                    reference_load[np.asarray(elements[index].dof_indices, dtype=np.intp)] += local
                    element_loads[index] += local
                continue
            raise ValueError(
                f"P13 plate adapter does not support {load.kind.value!r} load {load.id!r}"
            )

        reference_load.setflags(write=False)
        for element_load in element_loads:
            element_load.setflags(write=False)
        return _PlateSystem(
            elements=tuple(elements),
            reference_load=reference_load,
            element_reference_loads=tuple(element_loads),
        )

    def _require_family(self, model: ModelInput) -> None:
        if not isinstance(model, ModelInput):
            raise TypeError("model must be a validated nonlinear_core.ModelInput")
        if model.model_family is not ModelFamily.PLATE:
            raise ValueError(
                f"{self.adapter_id} requires family 'plate'; got {model.model_family.value!r}"
            )

    def _require_compatible_state(self, model: ModelInput, state: AdapterState) -> None:
        if state.model_id != model.model_id or state.adapter_id != self.adapter_id:
            raise ValueError("committed_state belongs to a different model or adapter")


__all__ = ["VonKarmanPlateAdapter"]
