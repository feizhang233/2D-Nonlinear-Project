"""P9 adapter for the corotational Euler-Bernoulli frame element."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

import numpy as np
from numpy.typing import ArrayLike, NDArray

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
    LocalFailure,
    ModelResponse,
)
from nonlinear_core.constants import PACKAGE_VERSION
from nonlinear_core.contracts import canonical_model_json
from nonlinear_core.elements import (
    CorotationalFrameCollapseError,
    evaluate_corotational_frame,
)
from nonlinear_core.model import CoordinateSystem, DofRef, LoadKind, ModelFamily, ModelInput
from nonlinear_core.result import SolveResult, StepStatus
from reused_cores.frame2d_linear import (
    FrameElement,
    Node,
    calculate_geometry,
    calculate_transformation,
)

FloatArray = NDArray[np.float64]


@dataclass(frozen=True, slots=True)
class FramePathPoint:
    step_index: int
    load_factor: float
    displacement: float
    control_method: str


@dataclass(frozen=True, slots=True)
class _FrameSystem:
    nodes: tuple[Node, ...]
    elements: tuple[FrameElement, ...]
    element_ids: tuple[str, ...]
    element_dofs: tuple[tuple[int, ...], ...]
    reference_load: FloatArray
    element_reference_loads: tuple[FloatArray, ...]


def _vector(value: ArrayLike, *, size: int) -> FloatArray:
    result = np.array(value, dtype=float, copy=True)
    if result.shape != (size,) or not np.all(np.isfinite(result)):
        raise ValueError(f"frame displacement must be a finite vector with shape ({size},)")
    result.setflags(write=False)
    return result


def _consistent_local_distributed_load(
    length: float,
    qx_i: float,
    qy_i: float,
    qx_j: float,
    qy_j: float,
) -> FloatArray:
    """Return the Euler-Bernoulli consistent vector for a linear local member load."""

    return np.asarray(
        [
            length * (2.0 * qx_i + qx_j) / 6.0,
            length * (7.0 * qy_i + 3.0 * qy_j) / 20.0,
            length**2 * (3.0 * qy_i + 2.0 * qy_j) / 60.0,
            length * (qx_i + 2.0 * qx_j) / 6.0,
            length * (3.0 * qy_i + 7.0 * qy_j) / 20.0,
            -(length**2) * (2.0 * qy_i + 3.0 * qy_j) / 60.0,
        ],
        dtype=float,
    )


def recover_frame_path(result: SolveResult, dof_index: int) -> tuple[FramePathPoint, ...]:
    """Extract accepted load-displacement points from a nonlinear solve result."""

    if isinstance(dof_index, bool) or not isinstance(dof_index, int) or dof_index < 0:
        raise ValueError("dof_index must be a non-negative integer")
    points: list[FramePathPoint] = []
    for step in result.steps:
        if step.status is not StepStatus.ACCEPTED:
            continue
        displacement = step.response.get("displacement")
        if displacement is None and step.iterations:
            displacement = step.iterations[-1].diagnostics.get("displacement")
        if not isinstance(displacement, (list, tuple)) or dof_index >= len(displacement):
            raise ValueError("accepted step does not retain the requested displacement")
        points.append(
            FramePathPoint(
                step_index=step.step_index,
                load_factor=step.load_factor,
                displacement=float(displacement[dof_index]),
                control_method=step.control_method.value,
            )
        )
    return tuple(points)


class CorotationalFrameAdapter:
    """Assemble objective elastic frame responses for the existing solver contract."""

    family = ModelFamily.FRAME
    adapter_id = "frame2d-corotational"
    core_package = "nonlinear-core-corotational-frame"
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
            history={"configuration": "reference", "strain_energy": 0.0},
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
        element_responses: list[ElementResponse] = []
        history: dict[str, object] = {}
        energy = 0.0
        stretches: list[float] = []
        reference_jacobians: list[float] = []
        for index, (element, element_id, dofs) in enumerate(
            zip(system.elements, system.element_ids, system.element_dofs, strict=True)
        ):
            indices = np.asarray(dofs, dtype=np.intp)
            local_displacement = vector[indices]
            node_i = system.nodes[element.node_i - 1]
            node_j = system.nodes[element.node_j - 1]
            local_failures: tuple[LocalFailure, ...] = ()
            try:
                response = evaluate_corotational_frame(
                    element,
                    node_i,
                    node_j,
                    local_displacement,
                )
            except CorotationalFrameCollapseError as error:
                local_failures = (
                    LocalFailure(
                        code="FRAME_CURRENT_LENGTH_COLLAPSED",
                        message=str(error),
                        element_id=element_id,
                    ),
                )
                local_internal = np.zeros(6, dtype=float)
                local_tangent = np.zeros((6, 6), dtype=float)
                local_energy = 0.0
                stretch = 0.0
                metadata: dict[str, object] = {
                    "formulation": "corotational-euler-bernoulli",
                    "reference_configuration": {"length": error.reference_length},
                    "current_configuration": {"length": error.current_length},
                }
            else:
                local_internal = response.internal_force
                local_tangent = response.tangent
                local_energy = response.strain_energy
                stretch = response.axial_stretch
                metadata = {
                    "formulation": "corotational-euler-bernoulli",
                    "kinematic_boundary": "large rotation, small elastic strain",
                    "reference_configuration": {
                        "length": response.reference_length,
                        "angle": response.reference_angle,
                    },
                    "current_configuration": {
                        "length": response.current_length,
                        "angle": response.current_angle,
                        "chord_rotation": response.chord_rotation,
                    },
                    "basic_deformation": [float(value) for value in response.basic_deformation],
                    "basic_force": [float(value) for value in response.basic_force],
                    "local_end_forces": [float(value) for value in response.local_end_forces],
                    "material_tangent_norm": float(np.linalg.norm(response.material_tangent)),
                    "geometric_tangent_norm": float(np.linalg.norm(response.geometric_tangent)),
                }
                history[element_id] = {
                    "current_length": response.current_length,
                    "current_angle": response.current_angle,
                    "basic_deformation": [float(value) for value in response.basic_deformation],
                }
            internal[indices] += local_internal
            tangent[np.ix_(indices, indices)] += local_tangent
            energy += local_energy
            stretches.append(stretch)
            reference_jacobians.append(calculate_geometry(element, node_i, node_j).L / 2.0)
            element_responses.append(
                ElementResponse(
                    element_id=element_id,
                    dof_indices=dofs,
                    internal_force=local_internal,
                    tangent=local_tangent,
                    external_force=factor * system.element_reference_loads[index],
                    energy=local_energy,
                    min_det_j=reference_jacobians[-1],
                    min_det_f=stretch,
                    local_failures=local_failures,
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
                "load_factor": factor,
                "strain_energy": energy,
                "elements": history,
            },
        )
        return ModelResponse(
            internal_force=internal,
            tangent=tangent,
            external_force=external,
            external_tangent=None,
            trial_state=trial_state,
            elements=tuple(element_responses),
            strain_energy=energy,
            min_det_j=min(reference_jacobians),
            min_det_f=min(stretches),
            # Element failures stay attached to their owning element.  Repeating them
            # here would make the solver count and report the same failure twice.
            local_failures=(),
            metadata={
                "formulation": "corotational-euler-bernoulli",
                "configuration": "current",
                "reference_load_type": "fixed-reference nodal/consistent-distributed",
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
                    **dict(item.metadata),
                }
                for item in response.elements
            ),
            metadata={
                "adapter_id": self.adapter_id,
                "load_factor": float(load_factor),
                "reference_configuration": "model.nodes",
                "current_configuration": "model.nodes + displacement",
            },
        )

    def _build_system(self, model: ModelInput) -> _FrameSystem:
        self._require_family(model)
        if (
            model.units.length != "m"
            or model.units.force != "N"
            or model.units.stress != "Pa"
            or model.units.angle != "rad"
        ):
            raise ValueError("corotational frame adapter requires SI labels m/N/Pa/rad")
        node_indices = node_index_lookup(model)
        native_nodes = tuple(
            Node(index + 1, float(node.coordinates[0]), float(node.coordinates[1]))
            for index, node in enumerate(model.nodes)
        )
        materials = material_lookup(model)
        native_elements: list[FrameElement] = []
        element_dofs: list[tuple[int, ...]] = []
        for index, common in enumerate(model.elements):
            formulation = common.formulation.strip().lower()
            if "corotational" not in formulation or len(common.node_ids) != 2:
                raise ValueError(
                    f"frame element {common.id!r} must use a two-node corotational formulation"
                )
            material = materials[common.material_id]
            if material.model.strip().lower() not in {"linear-elastic", "elastic"}:
                raise ValueError(f"frame material {material.id!r} must be linear-elastic for P9")
            node_i = node_indices[common.node_ids[0]]
            node_j = node_indices[common.node_ids[1]]
            native = FrameElement(
                index + 1,
                node_i + 1,
                node_j + 1,
                float_value(material.parameters, "young", "young_modulus", "E"),
                float_value(common.properties, "area", "A"),
                float_value(common.properties, "second_moment", "moment_of_inertia", "I"),
            )
            calculate_geometry(native, native_nodes[node_i], native_nodes[node_j])
            native_elements.append(native)
            element_dofs.append(
                (
                    3 * node_i,
                    3 * node_i + 1,
                    3 * node_i + 2,
                    3 * node_j,
                    3 * node_j + 1,
                    3 * node_j + 2,
                )
            )

        size = 3 * len(native_nodes)
        reference_load = np.zeros(size, dtype=float)
        owners = first_connected_elements(model)
        element_lookup = {element.id: index for index, element in enumerate(model.elements)}
        element_loads = [np.zeros(6, dtype=float) for _ in native_elements]
        for load in model.loads:
            follower = load.extensions.get("follower") is True
            configuration_dependent = load.extensions.get("configuration_dependent") is True
            if follower or configuration_dependent:
                raise ValueError(
                    "P9 corotational frame supports fixed reference loads only; "
                    "follower/configuration-dependent loads remain outside scope"
                )
            components = scaled_components(load)
            if load.kind is LoadKind.NODAL:
                if load.coordinate_system is not CoordinateSystem.GLOBAL:
                    raise ValueError(f"frame nodal load {load.id!r} must use global coordinates")
                assert load.node_id is not None
                node_index = node_indices[load.node_id]
                values = np.asarray(
                    [
                        components.get("UX", 0.0),
                        components.get("UY", 0.0),
                        components.get("RZ", 0.0),
                    ]
                )
                reference_load[3 * node_index : 3 * node_index + 3] += values
                owner_index = element_lookup[owners[load.node_id]]
                owner = model.elements[owner_index]
                local_node = owner.node_ids.index(load.node_id)
                element_loads[owner_index][3 * local_node : 3 * local_node + 3] += values
                continue
            if load.kind not in {LoadKind.ELEMENT, LoadKind.EDGE}:
                raise ValueError(
                    f"P9 corotational frame does not support {load.kind.value!r} load {load.id!r}"
                )
            if load.coordinate_system is not CoordinateSystem.LOCAL:
                raise ValueError(
                    f"frame distributed load {load.id!r} must use coordinate_system='local'"
                )
            assert load.element_id is not None
            owner_index = element_lookup[load.element_id]
            element = native_elements[owner_index]
            geometry = calculate_geometry(
                element,
                native_nodes[element.node_i - 1],
                native_nodes[element.node_j - 1],
            )
            qx_i = components.get("qx_i", components.get("UX", 0.0))
            qy_i = components.get("qy_i", components.get("UY", 0.0))
            local_force = _consistent_local_distributed_load(
                geometry.L,
                qx_i,
                qy_i,
                components.get("qx_j", qx_i),
                components.get("qy_j", qy_i),
            )
            global_force = calculate_transformation(geometry).T @ local_force
            indices = np.asarray(element_dofs[owner_index], dtype=np.intp)
            reference_load[indices] += global_force
            element_loads[owner_index] += global_force

        reference_load.setflags(write=False)
        for value in element_loads:
            value.setflags(write=False)
        return _FrameSystem(
            nodes=native_nodes,
            elements=tuple(native_elements),
            element_ids=tuple(element.id for element in model.elements),
            element_dofs=tuple(element_dofs),
            reference_load=reference_load,
            element_reference_loads=tuple(element_loads),
        )

    def _require_family(self, model: ModelInput) -> None:
        if not isinstance(model, ModelInput):
            raise TypeError("model must be a validated nonlinear_core.ModelInput")
        if model.model_family is not ModelFamily.FRAME:
            raise ValueError("corotational frame adapter requires model_family='frame'")

    def _require_compatible_state(self, model: ModelInput, state: AdapterState) -> None:
        if state.model_id != model.model_id or state.adapter_id != self.adapter_id:
            raise ValueError("committed_state belongs to a different model or adapter")


__all__ = ["CorotationalFrameAdapter", "FramePathPoint", "recover_frame_path"]
