"""P7 raw recovery plus the P8 derived-nodal switch.

``recover_results`` does not modify ``SolveResult``. Gauss-point fields stay in
the element local basis. Derived nodal values are appended only when requested.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from reused_cores.shell3d_linear.assembly import (
    AssembledSystem,
    ElementContribution,
    assemble_system,
    extract_element_vector,
    matrix_vector_product,
)
from reused_cores.shell3d_linear.constants import CORE_VERSION, GAUSS_POINT_IDS, GLOBAL_DOF_ORDER, SCHEMA_VERSION
from reused_cores.shell3d_linear.diagnostics import Diagnostic, make_diagnostic, sort_diagnostics
from reused_cores.shell3d_linear.drilling import global_shell_energy
from reused_cores.shell3d_linear.membrane_bending import evaluate_membrane_bending_response
from reused_cores.shell3d_linear.post import derive_nodal_results, derived_diagnostics
from reused_cores.shell3d_linear.shear import evaluate_shear_response
from reused_cores.shell3d_linear.solve import LinearStaticResult, characteristic_scales
from reused_cores.shell3d_linear.transformation import global_to_local_dofs
from reused_cores.shell3d_linear.types import (
    AnalysisResult,
    BalanceReport,
    ElementEnergy,
    ElementResult,
    GaussPointResult,
    NodalReaction,
    PostOptions,
    PostResult,
    ResidualReport,
    ResultSource,
    SolveResult,
    ValidatedModel,
    Vec3,
)

_POINT_IDS = set(GAUSS_POINT_IDS)


@dataclass(frozen=True, slots=True)
class RecoveryResult:
    """P7 recovery outcome. Failed runs omit forged element or balance data."""

    status: Literal["succeeded", "failed"]
    diagnostics: tuple[Diagnostic, ...]
    analysis_result: AnalysisResult
    element_results: tuple[ElementResult, ...] | None
    balance: BalanceReport | None
    post_result: PostResult | None

    @property
    def errors(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "error")

    @property
    def warnings(self) -> tuple[Diagnostic, ...]:
        return tuple(item for item in self.diagnostics if item.severity == "warning")


def _finite(value: float) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _all_finite(values: Sequence[float]) -> bool:
    return all(_finite(value) for value in values)


def _norm2(values: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in values))


def _cross(left: Sequence[float], right: Sequence[float]) -> Vec3:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _add3(left: Sequence[float], right: Sequence[float]) -> Vec3:
    return (left[0] + right[0], left[1] + right[1], left[2] + right[2])


def _centroid(points: Sequence[Sequence[float]]) -> Vec3:
    count = len(points)
    if count == 0:
        return (0.0, 0.0, 0.0)
    return (
        sum(point[0] for point in points) / count,
        sum(point[1] for point in points) / count,
        sum(point[2] for point in points) / count,
    )


def displacement_vector_from_solve(
    model: ValidatedModel,
    solve_result: SolveResult,
) -> tuple[float, ...]:
    """Rebuild the global displacement vector in input-node 6-DOF order."""

    by_id = {item.node_id: item for item in solve_result.displacements}
    if len(by_id) != len(solve_result.displacements):
        raise ValueError("SolveResult contains duplicate node displacements")
    missing = [node.id for node in model.nodes if node.id not in by_id]
    if missing:
        raise ValueError(f"SolveResult is missing displacements for {missing!r}")
    extra = sorted(set(by_id) - {node.id for node in model.nodes})
    if extra:
        raise ValueError(f"SolveResult has unexpected node ids {extra!r}")
    values = [0.0] * (6 * len(model.nodes))
    for node in model.nodes:
        item = by_id[node.id]
        values[node.dof_indices[0]] = item.translation_global[0]
        values[node.dof_indices[1]] = item.translation_global[1]
        values[node.dof_indices[2]] = item.translation_global[2]
        values[node.dof_indices[3]] = item.rotation_global[0]
        values[node.dof_indices[4]] = item.rotation_global[1]
        values[node.dof_indices[5]] = item.rotation_global[2]
    return tuple(values)


def recover_element_result(
    contribution: ElementContribution,
    global_displacement: Sequence[float],
    *,
    shear_formulation: str,
) -> ElementResult:
    """Recover one element's local DOFs, Gauss fields and energy split."""

    element_global = extract_element_vector(global_displacement, contribution.dof_indices)
    local_dofs = global_to_local_dofs(contribution.operator.transform, element_global)
    membrane = evaluate_membrane_bending_response(
        contribution.geometry,
        contribution.constitutive,
        local_dofs,
    )
    shear = evaluate_shear_response(
        contribution.geometry,
        contribution.constitutive,
        local_dofs,
        formulation=shear_formulation,
    )
    energy = global_shell_energy(contribution.operator, element_global)
    points: list[GaussPointResult] = []
    for mapped, membrane_point, shear_point in zip(
        contribution.geometry.gauss_points,
        membrane.gauss_points,
        shear.gauss_points,
        strict=True,
    ):
        if mapped.point_id not in _POINT_IDS:
            raise ValueError(f"unexpected Gauss point id {mapped.point_id!r}")
        points.append(
            GaussPointResult(
                point_id=mapped.point_id,  # type: ignore[arg-type]
                natural_coordinates=mapped.natural,
                local_coordinates=mapped.local_xy,
                weight=mapped.weight,
                det_jacobian=mapped.jacobian.det_j,
                membrane_strain=membrane_point.membrane_strain,
                curvature=membrane_point.curvature,
                assumed_shear_strain=shear_point.shear_strain,
                membrane_resultant=membrane_point.membrane_resultant,
                bending_resultant=membrane_point.bending_resultant,
                shear_resultant=shear_point.shear_resultant,
                stress_top=membrane_point.surface_stresses.top,
                stress_bottom=membrane_point.surface_stresses.bottom,
            )
        )
    if len(points) != 4:
        raise ValueError("element recovery requires exactly four Gauss points")
    return ElementResult(
        element_id=contribution.element_id,
        coordinate_system="element_local",
        local_basis=contribution.geometry.basis.lambda_rows,
        local_dofs=local_dofs,
        gauss_points=(points[0], points[1], points[2], points[3]),
        energy=ElementEnergy(
            membrane=energy.membrane,
            bending=energy.bending,
            shear=energy.shear,
            drilling=energy.drilling,
            total=energy.total,
        ),
    )


def _element_results_are_finite(results: Sequence[ElementResult]) -> bool:
    for item in results:
        if not _all_finite(item.local_dofs):
            return False
        energy = item.energy
        if not _all_finite(
            (energy.membrane, energy.bending, energy.shear, energy.drilling, energy.total)
        ):
            return False
        if abs(
            energy.total - (energy.membrane + energy.bending + energy.shear + energy.drilling)
        ) > (1e-12 * max(1.0, abs(energy.total))):
            return False
        for point in item.gauss_points:
            if not (
                _finite(point.weight)
                and _finite(point.det_jacobian)
                and _all_finite(point.natural_coordinates)
                and _all_finite(point.local_coordinates)
                and _all_finite(point.membrane_strain)
                and _all_finite(point.curvature)
                and _all_finite(point.assumed_shear_strain)
                and _all_finite(point.membrane_resultant)
                and _all_finite(point.bending_resultant)
                and _all_finite(point.shear_resultant)
                and _all_finite(point.stress_top)
                and _all_finite(point.stress_bottom)
            ):
                return False
    return True


def _nodal_force_moment(
    values: Sequence[float],
    base: int,
) -> tuple[Vec3, Vec3]:
    return (
        (values[base], values[base + 1], values[base + 2]),
        (values[base + 3], values[base + 4], values[base + 5]),
    )


def build_balance_report(
    model: ValidatedModel,
    assembled: AssembledSystem,
    displacement: Sequence[float],
    residual: Sequence[float],
    element_results: Sequence[ElementResult],
    *,
    reference: Sequence[float],
) -> BalanceReport:
    """Assemble the P0 force, moment and work identities from recovered fields."""

    applied_force = (0.0, 0.0, 0.0)
    reaction_force = (0.0, 0.0, 0.0)
    applied_moment = (0.0, 0.0, 0.0)
    reaction_moment = (0.0, 0.0, 0.0)
    applied_force_abs = 0.0
    reaction_force_abs = 0.0
    applied_moment_abs = 0.0
    reaction_moment_abs = 0.0
    constrained = {item.node_id for item in model.constraints}
    for node in model.nodes:
        base = node.dof_indices[0]
        force, moment = _nodal_force_moment(assembled.applied_load, base)
        lever = (
            node.coordinates[0] - reference[0],
            node.coordinates[1] - reference[1],
            node.coordinates[2] - reference[2],
        )
        couple = _add3(_cross(lever, force), moment)
        applied_force = _add3(applied_force, force)
        applied_moment = _add3(applied_moment, couple)
        applied_force_abs += _norm2(force)
        applied_moment_abs += _norm2(couple)
        if node.id not in constrained:
            continue
        reaction, reaction_m = _nodal_force_moment(residual, base)
        reaction_couple = _add3(_cross(lever, reaction), reaction_m)
        reaction_force = _add3(reaction_force, reaction)
        reaction_moment = _add3(reaction_moment, reaction_couple)
        reaction_force_abs += _norm2(reaction)
        reaction_moment_abs += _norm2(reaction_couple)

    total_energy = sum(item.energy.total for item in element_results)
    external_work = sum(
        displacement[index] * assembled.applied_load[index] for index in range(assembled.dof_count)
    )
    constraint_work = sum(
        displacement[item.dof_index] * residual[item.dof_index] for item in model.constraints
    )
    force_error = _norm2(_add3(applied_force, reaction_force)) / max(
        applied_force_abs, reaction_force_abs, 1.0
    )
    moment_error = _norm2(_add3(applied_moment, reaction_moment)) / max(
        applied_moment_abs,
        reaction_moment_abs,
        max(applied_force_abs, reaction_force_abs, 1.0) * assembled.characteristic_length,
        1.0,
    )
    complete_work = external_work + constraint_work
    energy_error = abs(2.0 * total_energy - complete_work) / max(
        2.0 * abs(total_energy), abs(complete_work), 1.0
    )
    return BalanceReport(
        moment_reference_point_global=(reference[0], reference[1], reference[2]),
        applied_force_global=applied_force,
        applied_moment_global=applied_moment,
        reaction_force_global=reaction_force,
        reaction_moment_global=reaction_moment,
        force_relative_error=force_error,
        moment_relative_error=moment_error,
        total_strain_energy=total_energy,
        external_work_u_dot_f=external_work,
        energy_identity_relative_error=energy_error,
    )


def _source(model: ValidatedModel) -> ResultSource:
    return ResultSource(
        model_id=model.model_id,
        load_case_id=model.load_case_id,
        model_sha256=model.model_sha256,
        core_version=CORE_VERSION,
    )


def _failed_analysis(
    model: ValidatedModel,
    diagnostics: Sequence[Diagnostic],
) -> RecoveryResult:
    ordered = sort_diagnostics(list(diagnostics))
    analysis = AnalysisResult(
        document_type="analysis_result",
        schema_version=SCHEMA_VERSION,
        status="failed",
        source=_source(model),
        units=model.units,
        diagnostics=ordered,
    )
    return RecoveryResult(
        status="failed",
        diagnostics=ordered,
        analysis_result=analysis,
        element_results=None,
        balance=None,
        post_result=None,
    )


def _recovery_diagnostic(
    code: str,
    *,
    observed: object,
    threshold: object,
    json_path: str,
    message: str,
    unit: str | None = None,
) -> Diagnostic:
    return make_diagnostic(
        code,
        entity_type="postprocess",
        entity_id=None,
        json_path=json_path,
        observed=observed,
        threshold=threshold,
        unit=unit,
        message=message,
    )


def _valid_post_reference(options: PostOptions) -> bool:
    reference = options.moment_reference_point_global
    if reference is None:
        return True
    try:
        return len(reference) == 3 and _all_finite(reference)
    except TypeError:
        return False


def _solve_metadata_is_frozen(solve_result: SolveResult) -> bool:
    return (
        solve_result.solver_status == "succeeded"
        and solve_result.method == "symmetric_direct"
        and solve_result.scaling == "characteristic_length"
        and solve_result.precision == "float64"
        and solve_result.dof_order_global == GLOBAL_DOF_ORDER
    )


def _assembled_matches_model(model: ValidatedModel, assembled: AssembledSystem) -> bool:
    return (
        assembled.model_id == model.model_id
        and assembled.load_case_id == model.load_case_id
        and assembled.model_sha256 == model.model_sha256
    )


def _recovery_backward_error(
    assembled: AssembledSystem,
    displacement: Sequence[float],
    residual: Sequence[float],
) -> float:
    scales = characteristic_scales(assembled.dof_count, assembled.characteristic_length)
    constrained = {item.dof_index for item in assembled.constraints}
    free = tuple(index for index in range(assembled.dof_count) if index not in constrained)
    if not free:
        return 0.0
    internal = matrix_vector_product(assembled.stiffness, displacement)
    scaled_residual = [scales[index] * residual[index] for index in free]
    scaled_internal = [scales[index] * internal[index] for index in free]
    scaled_applied = [scales[index] * assembled.applied_load[index] for index in free]
    denominator = max(_norm2(scaled_internal), _norm2(scaled_applied), 1.0)
    return _norm2(scaled_residual) / denominator


def _canonical_solve_result(
    model: ValidatedModel,
    original: SolveResult,
    residual: Sequence[float],
    backward_error: float,
    balance: BalanceReport,
) -> SolveResult:
    constrained_nodes = {item.node_id for item in model.constraints}
    reactions = tuple(
        NodalReaction(
            node_id=node.id,
            force_global=(
                residual[node.dof_indices[0]],
                residual[node.dof_indices[1]],
                residual[node.dof_indices[2]],
            ),
            moment_global=(
                residual[node.dof_indices[3]],
                residual[node.dof_indices[4]],
                residual[node.dof_indices[5]],
            ),
        )
        for node in model.nodes
        if node.id in constrained_nodes
    )
    return SolveResult(
        solver_status="succeeded",
        method="symmetric_direct",
        scaling="characteristic_length",
        precision="float64",
        dof_order_global=GLOBAL_DOF_ORDER,
        displacements=original.displacements,
        reactions=reactions,
        residual=ResidualReport(
            scaled_relative_backward_error=backward_error,
            force_equilibrium_relative_error=balance.force_relative_error,
            moment_equilibrium_relative_error=balance.moment_relative_error,
            condition_estimate=original.residual.condition_estimate,
        ),
    )


def recover_results(
    model: ValidatedModel,
    solve: SolveResult | LinearStaticResult,
    post_options: PostOptions | None = None,
) -> RecoveryResult:
    """Recover raw element results and, optionally, derived nodal resultants."""

    options = post_options or PostOptions()
    if not _valid_post_reference(options):
        diagnostics = list(model.diagnostics)
        diagnostics.append(
            _recovery_diagnostic(
                "SHELL-NUM-E001",
                observed=repr(options.moment_reference_point_global),
                threshold="three finite global coordinates",
                json_path="$.post_options.moment_reference_point_global",
                unit="m",
                message="The moment reference point must contain three finite coordinates.",
            )
        )
        return _failed_analysis(model, diagnostics)

    if isinstance(solve, LinearStaticResult):
        diagnostics = list(solve.diagnostics)
        if solve.status != "succeeded" or solve.solve_result is None:
            return _failed_analysis(model, diagnostics)
        solve_result = solve.solve_result
        assembled = solve.assembled or assemble_system(model)
        if not _assembled_matches_model(model, assembled):
            diagnostics.append(
                _recovery_diagnostic(
                    "SHELL-SOLVE-E001",
                    observed={
                        "assembled_model_id": assembled.model_id,
                        "assembled_load_case_id": assembled.load_case_id,
                        "assembled_model_sha256": assembled.model_sha256,
                    },
                    threshold={
                        "model_id": model.model_id,
                        "load_case_id": model.load_case_id,
                        "model_sha256": model.model_sha256,
                    },
                    json_path="$.source",
                    unit=None,
                    message="The solve result belongs to a different validated model.",
                )
            )
            return _failed_analysis(model, diagnostics)
        try:
            serialized_displacement = displacement_vector_from_solve(model, solve_result)
        except ValueError as exc:
            diagnostics.append(
                _recovery_diagnostic(
                    "SHELL-SOLVE-E001",
                    observed=str(exc),
                    threshold="one displacement record per model node",
                    json_path="$.solve_result.displacements",
                    unit=None,
                    message="The solve result is incompatible with the validated model.",
                )
            )
            return _failed_analysis(model, diagnostics)
        if (
            solve.displacement_vector is not None
            and solve.displacement_vector != serialized_displacement
        ):
            diagnostics.append(
                _recovery_diagnostic(
                    "SHELL-SOLVE-E001",
                    observed="internal and serialized displacement vectors differ",
                    threshold="one deterministic displacement vector",
                    json_path="$.solve_result.displacements",
                    unit=None,
                    message="The solve result contains inconsistent displacement representations.",
                )
            )
            return _failed_analysis(model, diagnostics)
        displacement = serialized_displacement
    else:
        diagnostics = list(model.diagnostics)
        solve_result = solve
        assembled = assemble_system(model)
        try:
            displacement = displacement_vector_from_solve(model, solve_result)
        except ValueError as exc:
            diagnostics.append(
                _recovery_diagnostic(
                    "SHELL-SOLVE-E001",
                    observed=str(exc),
                    threshold="one displacement record per model node",
                    json_path="$.solve_result.displacements",
                    unit=None,
                    message="The solve result is incompatible with the validated model.",
                )
            )
            return _failed_analysis(model, diagnostics)

    if not _solve_metadata_is_frozen(solve_result):
        diagnostics.append(
            _recovery_diagnostic(
                "SHELL-SCHEMA-E001",
                observed={
                    "solver_status": solve_result.solver_status,
                    "method": solve_result.method,
                    "scaling": solve_result.scaling,
                    "precision": solve_result.precision,
                    "dof_order_global": solve_result.dof_order_global,
                },
                threshold="frozen P0 SolveResult metadata",
                json_path="$.solve_result",
                unit=None,
                message="The solve result metadata does not match the frozen P0 contract.",
            )
        )
        return _failed_analysis(model, diagnostics)

    internal = matrix_vector_product(assembled.stiffness, displacement)
    residual = tuple(
        left - right for left, right in zip(internal, assembled.applied_load, strict=True)
    )
    recovery_backward = _recovery_backward_error(assembled, displacement, residual)
    recovery_tolerance = assembled.analysis_options.solver.relative_backward_error_tolerance
    if not math.isfinite(recovery_backward) or recovery_backward > recovery_tolerance:
        diagnostics.append(
            _recovery_diagnostic(
                "SHELL-SOLVE-E002",
                observed=recovery_backward,
                threshold=recovery_tolerance,
                json_path="$.solve_result.residual.scaled_relative_backward_error",
                unit="1",
                message=(
                    "The supplied displacement field does not satisfy "
                    "the current model equilibrium."
                ),
            )
        )
        return _failed_analysis(model, diagnostics)

    shear_formulation = assembled.analysis_options.shear_formulation
    element_results = tuple(
        recover_element_result(
            contribution,
            displacement,
            shear_formulation=shear_formulation,
        )
        for contribution in assembled.elements
    )
    if not _element_results_are_finite(element_results) or not _all_finite(displacement):
        diagnostics.append(
            make_diagnostic(
                "SHELL-SOLVE-E001",
                entity_type="solver",
                entity_id=None,
                json_path="$.analysis_options.solver",
                observed="non-finite recovered fields",
                threshold="finite Gauss-point and energy values",
                unit=None,
            )
        )
        return _failed_analysis(model, diagnostics)

    reference = options.moment_reference_point_global or _centroid(
        [node.coordinates for node in model.nodes]
    )
    balance = build_balance_report(
        model,
        assembled,
        displacement,
        residual,
        element_results,
        reference=reference,
    )
    solve_result = _canonical_solve_result(
        model,
        solve_result,
        residual,
        recovery_backward,
        balance,
    )
    derived = ()
    if options.include_derived_nodal_results:
        try:
            derived = derive_nodal_results(model, assembled, element_results)
        except ValueError as exc:
            diagnostics.append(
                _recovery_diagnostic(
                    "SHELL-SOLVE-E001",
                    observed=str(exc),
                    threshold="recoverable element-to-node topology",
                    json_path="$.post_result.derived_nodal_results",
                    unit=None,
                    message="Derived nodal recovery failed for the validated topology.",
                )
            )
            return _failed_analysis(model, diagnostics)
        diagnostics.extend(derived_diagnostics(derived))
    post_result = PostResult(
        raw_element_results_ref="element_results",
        derived_nodal_results=derived,
    )
    ordered = sort_diagnostics(diagnostics)
    analysis = AnalysisResult(
        document_type="analysis_result",
        schema_version=SCHEMA_VERSION,
        status="succeeded",
        source=_source(model),
        units=model.units,
        diagnostics=ordered,
        solve_result=solve_result,
        element_results=element_results,
        balance=balance,
        post_result=post_result,
    )
    return RecoveryResult(
        status="succeeded",
        diagnostics=ordered,
        analysis_result=analysis,
        element_results=element_results,
        balance=balance,
        post_result=post_result,
    )


__all__ = [
    "RecoveryResult",
    "build_balance_report",
    "displacement_vector_from_solve",
    "recover_element_result",
    "recover_results",
]
