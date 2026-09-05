"""Adapters from the four existing math-core layouts to one request envelope."""

from __future__ import annotations

import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path
from typing import Any

import numpy as np

from .contracts import CoreMetadata, InterfaceError, OperationSpec

Handler = Callable[[Mapping[str, Any]], Any]
STEP2_ROOT = Path(__file__).resolve().parents[1]

PLATE_ROOT = STEP2_ROOT / "Plate-Shell-Buckling/Plate-Shell-Buckling/python_math_core"
INSTABILITY_ROOT = (
    STEP2_ROOT
    / "Shell-Instability-Research_Math-Core-Guide"
    / "Shell-Instability-Research_Math-Core-Guide"
    / "09_Python数学核心"
)
CONSTITUTIVE_ROOT = (
    STEP2_ROOT
    / "Constitutive Nonlinearity"
    / "Constitutive-Nonlinearity_Weeks10-14_Core-Guide"
    / "04_可复现算例"
)
GENERAL_SHELL_ROOT = (
    STEP2_ROOT
    / "General Nonlinear Shell"
    / "4_General-Nonlinear-Shell_16-24周"
    / "08_Python数学核心"
)


@dataclass(frozen=True)
class CoreAdapter:
    metadata: CoreMetadata
    handlers: Mapping[str, Handler]

    def run(self, operation: str, parameters: Mapping[str, Any]) -> Any:
        try:
            handler = self.handlers[operation]
        except KeyError as exc:
            raise InterfaceError(
                "UNKNOWN_OPERATION",
                f"core {self.metadata.core_id!r} does not support operation {operation!r}",
                details={"supported": sorted(self.handlers)},
            ) from exc
        return handler(parameters)


def _import_from(root: Path, module_name: str):
    root_text = str(root)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)
    try:
        return import_module(module_name)
    except Exception as exc:  # pragma: no cover - retained as a stable integration error
        raise InterfaceError(
            "CORE_IMPORT_FAILED",
            f"could not import {module_name!r} from {root}",
            details={"exception": f"{type(exc).__name__}: {exc}"},
        ) from exc


def _arguments(
    parameters: Mapping[str, Any],
    *,
    required: tuple[str, ...] = (),
    optional: tuple[str, ...] = (),
) -> dict[str, Any]:
    missing = [name for name in required if name not in parameters]
    if missing:
        raise InterfaceError(
            "MISSING_PARAMETER",
            "required parameters are missing",
            details={"missing": missing},
        )
    allowed = set(required) | set(optional)
    unknown = sorted(set(parameters) - allowed)
    if unknown:
        raise InterfaceError(
            "UNKNOWN_PARAMETER",
            "request contains unsupported parameters",
            details={"unknown": unknown, "allowed": sorted(allowed)},
        )
    return {name: parameters[name] for name in required + optional if name in parameters}


def _mapping(value: Any, *, name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise InterfaceError("INVALID_PARAMETER", f"{name} must be a mapping")
    return dict(value)


def _plate_verify(parameters: Mapping[str, Any]) -> dict[str, Any]:
    _arguments(parameters)
    verification = _import_from(PLATE_ROOT, "plate_shell_buckling_core.verification")
    records = verification.run_validation_suite()
    return {
        "execution_ok": True,
        "all_records_passed": all(record.passed for record in records),
        "verification_ids": [record.test_id for record in records],
        "records": records,
    }


def _plate_analysis_level(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(parameters, required=("question_kind",))
    contracts = _import_from(PLATE_ROOT, "plate_shell_buckling_core.contracts")
    level = contracts.analysis_level_for(values["question_kind"])
    return {
        "analysis_level": level,
        "warning": "The level is a conclusion boundary, not proof that all required physics exist.",
    }


def _plate_linear_buckling(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(
        parameters,
        required=("material_stiffness", "geometric_stiffness"),
        optional=("spectral_tolerance",),
    )
    lba = _import_from(PLATE_ROOT, "plate_shell_buckling_core.lba")
    pairs = lba.solve_generalized_buckling(
        values.pop("material_stiffness"),
        values.pop("geometric_stiffness"),
        **values,
    )
    return {
        "analysis_level": "LBA",
        "eigenpairs": pairs,
        "sign_convention": "K_M phi = lambda K_G phi; K_G=-K_sigma_ref; compression positive",
    }


def _plate_uniaxial(parameters: Mapping[str, Any]) -> Any:
    values = _arguments(
        parameters,
        required=("a_mm", "b_mm", "thickness_mm", "young_mpa", "poisson"),
        optional=("max_m", "max_n"),
    )
    lba = _import_from(PLATE_ROOT, "plate_shell_buckling_core.lba")
    return lba.uniaxial_rectangular_plate(**values)


def _plate_imperfection(parameters: Mapping[str, Any]) -> Any:
    values = _arguments(
        parameters,
        required=("normal_mode", "amplitude_mm", "sign"),
        optional=("fixed_mask",),
    )
    imperfections = _import_from(PLATE_ROOT, "plate_shell_buckling_core.imperfections")
    normal_mode = values.pop("normal_mode")
    return imperfections.map_normal_imperfection(normal_mode, **values)


def _instability_verify(parameters: Mapping[str, Any]) -> dict[str, Any]:
    _arguments(parameters)
    _import_from(INSTABILITY_ROOT / "src", "shell_instability_math")
    runner = _import_from(INSTABILITY_ROOT, "run_validation_problems")
    results, _markdown = runner.calculate()
    statuses = {test_id: result.get("status") for test_id, result in results.items()}
    return {
        "execution_ok": True,
        "all_records_passed": all(status == "PASS" for status in statuses.values()),
        "verification_ids": sorted(statuses),
        "statuses": statuses,
        "records": results,
    }


def _instability_linear_buckling(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(
        parameters,
        required=("material_stiffness", "geometric_stiffness"),
        optional=("positive_only", "zero_tolerance"),
    )
    buckling = _import_from(INSTABILITY_ROOT / "src", "shell_instability_math.buckling")
    material = values.pop("material_stiffness")
    geometric = values.pop("geometric_stiffness")
    result = buckling.generalized_symmetric_eigenpairs(material, geometric, **values)
    return {
        "analysis_level": "LBA",
        "eigenpairs": result,
        "boundary": "This dense reference requires a symmetric positive-definite K_G.",
    }


def _instability_classify(parameters: Mapping[str, Any]) -> Any:
    values = _arguments(
        parameters,
        required=("tangent", "reference_load", "right_null_vector"),
        optional=(
            "left_null_vector",
            "projection_tolerance",
            "singular_value_tolerance",
            "null_residual_tolerance",
        ),
    )
    critical = _import_from(INSTABILITY_ROOT / "src", "shell_instability_math.critical")
    tangent = values.pop("tangent")
    reference_load = values.pop("reference_load")
    right_null = values.pop("right_null_vector")
    return critical.classify_singular_point(tangent, reference_load, right_null, **values)


def _instability_koiter(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(
        parameters,
        required=("imperfection_magnitudes",),
        optional=("coefficient",),
    )
    koiter = _import_from(INSTABILITY_ROOT / "src", "shell_instability_math.koiter")
    magnitudes = values.pop("imperfection_magnitudes")
    return {
        "load_factors": koiter.koiter_two_thirds_law(magnitudes, **values),
        "boundary": "Local single-mode asymptotic estimate; not a multimode imperfection scan.",
    }


def _instability_cylinder(parameters: Mapping[str, Any]) -> Any:
    values = _arguments(
        parameters,
        required=(
            "elastic_modulus_mpa",
            "poisson_ratio",
            "radius_mm",
            "thickness_mm",
            "length_mm",
        ),
    )
    benchmarks = _import_from(INSTABILITY_ROOT / "src", "shell_instability_math.benchmarks")
    return benchmarks.cylinder_axial_buckling(**values)


def _constitutive_module():
    return _import_from(CONSTITUTIVE_ROOT, "reference_material_point")


def _constitutive_verify(parameters: Mapping[str, Any]) -> dict[str, Any]:
    _arguments(parameters)
    results = _constitutive_module().run_reference_checks()
    verification_ids = sorted(key for key in results if key.startswith("V"))
    return {
        "execution_ok": True,
        "all_records_passed": len(verification_ids) == 12,
        "verification_ids": verification_ids,
        "records": results,
    }


def _j2_state(module: Any, value: Any):
    state = _mapping(value, name="committed_state")
    values = _arguments(state, required=("plastic_strain", "alpha"))
    return module.J2State(np.asarray(values["plastic_strain"], dtype=float), values["alpha"])


def _combined_state(module: Any, value: Any):
    state = _mapping(value, name="committed_state")
    values = _arguments(state, required=("plastic_strain", "alpha", "backstress"))
    return module.Combined1DState(**values)


def _constitutive_material_update(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(
        parameters,
        required=("model", "total_strain", "committed_state", "material"),
        optional=("options",),
    )
    module = _constitutive_module()
    model = values["model"]
    material = _mapping(values["material"], name="material")
    options = _mapping(values.get("options", {}), name="options")

    if model == "linear_j2":
        allowed = _arguments(options, optional=("yield_tolerance",))
        response = module.j2_update(
            np.asarray(values["total_strain"], dtype=float),
            _j2_state(module, values["committed_state"]),
            module.J2Parameters(**material),
            **allowed,
        )
        stress, tangent, trial_state, diagnostics = response
        return _material_response(stress, tangent, trial_state, diagnostics)

    if model == "voce_j2":
        allowed = _arguments(options, optional=("local_tolerance", "max_iterations"))
        response = module.j2_voce_update(
            np.asarray(values["total_strain"], dtype=float),
            _j2_state(module, values["committed_state"]),
            module.VoceJ2Parameters(**material),
            **allowed,
        )
        stress, tangent, trial_state, diagnostics = response
        return _material_response(stress, tangent, trial_state, diagnostics)

    if model == "combined_1d":
        allowed = _arguments(options, optional=("yield_tolerance",))
        response = module.combined_1d_update(
            values["total_strain"],
            _combined_state(module, values["committed_state"]),
            module.Combined1DParameters(**material),
            **allowed,
        )
        stress, tangent, trial_state, diagnostics = response
        return _material_response(stress, tangent, trial_state, diagnostics)

    if model == "plane_stress_j2":
        allowed = _arguments(options, optional=("local_tolerance", "max_iterations"))
        response = module.plane_stress_update(
            np.asarray(values["total_strain"], dtype=float),
            _j2_state(module, values["committed_state"]),
            module.J2Parameters(**material),
            **allowed,
        )
        epsilon_zz, stress, tangent, trial_state, diagnostics = response
        result = _material_response(stress, tangent, trial_state, diagnostics)
        result["epsilon_zz"] = epsilon_zz
        return result

    raise InterfaceError(
        "INVALID_PARAMETER",
        f"unsupported constitutive model {model!r}",
        details={"supported": ["linear_j2", "voce_j2", "combined_1d", "plane_stress_j2"]},
    )


def _material_response(
    stress: Any, tangent: Any, trial_state: Any, diagnostics: Any
) -> dict[str, Any]:
    return {
        "stress": stress,
        "algorithmic_tangent": tangent,
        "trial_state": trial_state,
        "diagnostics": diagnostics,
        "commit_required": True,
    }


def _general_verify(parameters: Mapping[str, Any]) -> dict[str, Any]:
    _arguments(parameters)
    verification = _import_from(GENERAL_SHELL_ROOT, "general_nonlinear_shell_math.verification")
    records = verification.run_all_verifications()
    status_counts: dict[str, int] = {}
    for record in records:
        status_counts[record.status] = status_counts.get(record.status, 0) + 1
    return {
        "execution_ok": not any(record.status == "FAILED" for record in records),
        "all_stage_gates_passed": False,
        "verification_ids": [record.test_id for record in records],
        "status_counts": status_counts,
        "records": records,
        "boundary": (
            "PARTIAL, REFERENCE_ONLY, NOT_RUN, and AUDIT_RESULT are preserved as distinct states."
        ),
    }


def _general_rotation(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(
        parameters,
        required=("current_rotation", "increment"),
        optional=("increment_type",),
    )
    rotations = _import_from(GENERAL_SHELL_ROOT, "general_nonlinear_shell_math.rotations")
    current = values.pop("current_rotation")
    increment = values.pop("increment")
    rotation = rotations.update_rotation(current, increment, **values)
    return {"rotation": rotation, "metrics": rotations.rotation_metrics(rotation)}


def _general_material_update(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(
        parameters,
        required=("total_strain", "committed_state", "material"),
    )
    materials = _import_from(GENERAL_SHELL_ROOT, "general_nonlinear_shell_math.materials")
    state_values = _mapping(values["committed_state"], name="committed_state")
    state = materials.MaterialState1D(**state_values)
    material_values = _mapping(values["material"], name="material")
    model = materials.BilinearIsotropic1D(**material_values)
    response = model.evaluate(values["total_strain"], state)
    return {
        "stress": response.stress,
        "algorithmic_tangent": response.algorithmic_tangent,
        "trial_state": response.trial_state,
        "diagnostics": {
            "trial_stress": response.trial_stress,
            "yield_function_trial": response.yield_function_trial,
            "plastic_multiplier": response.plastic_multiplier,
            "yielded": response.yielded,
        },
        "commit_required": True,
    }


def _general_follower_load(parameters: Mapping[str, Any]) -> dict[str, Any]:
    values = _arguments(parameters, required=("x1", "x2", "pressure"))
    loads = _import_from(GENERAL_SHELL_ROOT, "general_nonlinear_shell_math.loads")
    return {
        "external_force": loads.follower_line_force(**values),
        "external_load_tangent": loads.follower_line_tangent(values["pressure"]),
        "tangent_may_be_nonsymmetric": True,
    }


def _general_plane_stress(parameters: Mapping[str, Any]) -> Any:
    values = _arguments(
        parameters,
        required=(
            "active_active",
            "active_thickness",
            "thickness_active",
            "thickness_thickness",
        ),
    )
    section = _import_from(GENERAL_SHELL_ROOT, "general_nonlinear_shell_math.section")
    return section.condense_plane_stress(**values)


def _general_arc_length(parameters: Mapping[str, Any]) -> Any:
    values = _arguments(
        parameters,
        required=("q_n", "load_factor_n", "arc_length"),
        optional=("beta", "reference_load", "direction", "tolerance", "max_iterations"),
    )
    continuation = _import_from(GENERAL_SHELL_ROOT, "general_nonlinear_shell_math.continuation")
    return continuation.solve_scalar_arc_length_step(**values)


def build_adapters() -> dict[str, CoreAdapter]:
    """Build the immutable registry without importing any optional core eagerly."""

    adapters = [
        CoreAdapter(
            metadata=CoreMetadata(
                core_id="plate_shell_buckling",
                title="Plate-Shell Buckling",
                version="0.1.0",
                source_path="Plate-Shell-Buckling/Plate-Shell-Buckling/python_math_core",
                scope="LBA, GNA reference paths, and GNIA imperfection preparation",
                residual_convention=(
                    "R=f_int-lambda*f_ref; K_M phi=lambda K_G phi; K_G=-K_sigma_ref"
                ),
                state_protocol=(
                    "No material history; path algorithms expose accepted/rejected-step evidence."
                ),
                verification_ids=tuple(f"V{index}" for index in range(10, 23)),
                verification_meaning=(
                    "ANALYTICAL_PASS or REFERENCE_CORE_PASS; never a production FE gate."
                ),
                limitations=(
                    "Not a universal curved-shell finite element.",
                    "LBA eigenvalues are not actual or design strengths.",
                    "GMNIA material, residual-stress, contact, and design-code checks are absent.",
                ),
                operations=(
                    OperationSpec("verify", "Run V10-V22."),
                    OperationSpec(
                        "analysis_level",
                        "Route a conclusion to LBA/GNA/GNIA/GMNIA.",
                        ("question_kind",),
                        example_parameters={"question_kind": "ideal_critical_mode"},
                    ),
                    OperationSpec(
                        "linear_buckling",
                        "Solve K_M phi=lambda K_G phi.",
                        ("material_stiffness", "geometric_stiffness"),
                        ("spectral_tolerance",),
                        {
                            "material_stiffness": [[12.0, -2.0], [-2.0, 6.0]],
                            "geometric_stiffness": [[1.0, 0.2], [0.2, 0.5]],
                        },
                    ),
                    OperationSpec(
                        "uniaxial_plate",
                        "Run the simply supported plate benchmark.",
                        ("a_mm", "b_mm", "thickness_mm", "young_mpa", "poisson"),
                        ("max_m", "max_n"),
                        {
                            "a_mm": 1000.0,
                            "b_mm": 500.0,
                            "thickness_mm": 10.0,
                            "young_mpa": 210000.0,
                            "poisson": 0.3,
                        },
                    ),
                    OperationSpec(
                        "imperfection_from_mode",
                        "Scale a normal mode to a length-valued imperfection.",
                        ("normal_mode", "amplitude_mm", "sign"),
                        ("fixed_mask",),
                        {
                            "normal_mode": [0.0, 1.0, -0.5],
                            "amplitude_mm": 2.0,
                            "sign": 1.0,
                        },
                    ),
                ),
            ),
            handlers={
                "verify": _plate_verify,
                "analysis_level": _plate_analysis_level,
                "linear_buckling": _plate_linear_buckling,
                "uniaxial_plate": _plate_uniaxial,
                "imperfection_from_mode": _plate_imperfection,
            },
        ),
        CoreAdapter(
            metadata=CoreMetadata(
                core_id="shell_instability",
                title="Shell Instability Research",
                version="0.1.0",
                source_path=(
                    "Shell-Instability-Research_Math-Core-Guide/"
                    "Shell-Instability-Research_Math-Core-Guide/09_Python数学核心"
                ),
                scope=(
                    "Critical-point classification, modal interaction, Koiter reduction, "
                    "and continuation references"
                ),
                residual_convention="R=f_int-lambda*f_ref; K_T*dq-f_ref*dlambda=-R",
                state_protocol=(
                    "Continuation does not own material state; callers must implement "
                    "trial/commit/rollback."
                ),
                verification_ids=tuple(f"V{index:02d}" for index in range(11)),
                verification_meaning=(
                    "PASS proves only the low-dimensional reference problem at its stated scope."
                ),
                limitations=(
                    "A tangent singularity is not automatically a bifurcation.",
                    "A smooth arc-length path is not automatically stable or unique.",
                    "Ideal cylinder and sphere values are not design strengths.",
                ),
                operations=(
                    OperationSpec("verify", "Run V00-V10."),
                    OperationSpec(
                        "linear_buckling",
                        "Run the dense generalized eigenvalue reference.",
                        ("material_stiffness", "geometric_stiffness"),
                        ("positive_only", "zero_tolerance"),
                        {
                            "material_stiffness": [[12.0, -2.0], [-2.0, 6.0]],
                            "geometric_stiffness": [[1.0, 0.2], [0.2, 0.5]],
                        },
                    ),
                    OperationSpec(
                        "classify_critical_point",
                        "Classify a verified single-nullity tangent.",
                        ("tangent", "reference_load", "right_null_vector"),
                        (
                            "left_null_vector",
                            "projection_tolerance",
                            "singular_value_tolerance",
                            "null_residual_tolerance",
                        ),
                        {
                            "tangent": [[0.0, 0.0], [0.0, 4.0]],
                            "reference_load": [2.0, 1.0],
                            "right_null_vector": [1.0, 0.0],
                        },
                    ),
                    OperationSpec(
                        "koiter_imperfection_law",
                        "Evaluate the local 2/3 imperfection law.",
                        ("imperfection_magnitudes",),
                        ("coefficient",),
                        {"imperfection_magnitudes": [0.0001, 0.001, 0.01]},
                    ),
                    OperationSpec(
                        "classical_cylinder",
                        "Evaluate the ideal axial-cylinder benchmark.",
                        (
                            "elastic_modulus_mpa",
                            "poisson_ratio",
                            "radius_mm",
                            "thickness_mm",
                            "length_mm",
                        ),
                        example_parameters={
                            "elastic_modulus_mpa": 210000.0,
                            "poisson_ratio": 0.3,
                            "radius_mm": 500.0,
                            "thickness_mm": 5.0,
                            "length_mm": 2000.0,
                        },
                    ),
                ),
            ),
            handlers={
                "verify": _instability_verify,
                "linear_buckling": _instability_linear_buckling,
                "classify_critical_point": _instability_classify,
                "koiter_imperfection_law": _instability_koiter,
                "classical_cylinder": _instability_cylinder,
            },
        ),
        CoreAdapter(
            metadata=CoreMetadata(
                core_id="constitutive_nonlinearity",
                title="Constitutive Nonlinearity",
                version="reference-1.0",
                source_path=(
                    "Constitutive Nonlinearity/"
                    "Constitutive-Nonlinearity_Weeks10-14_Core-Guide/04_可复现算例"
                ),
                scope=(
                    "Small-strain material-point updates: linear/Voce J2, plane stress, "
                    "and combined-hardening 1D"
                ),
                residual_convention=(
                    "Material local residual; stress/tangent follow true-tensor or scalar "
                    "conventions reported in diagnostics."
                ),
                state_protocol=(
                    "update(total_strain, committed_state, material, options) returns stress, "
                    "tangent, trial_state, diagnostics without mutation."
                ),
                verification_ids=tuple(f"V{index:02d}" for index in range(12)),
                verification_meaning=(
                    "V00-V11 material-point reference checks; not a production material library."
                ),
                limitations=(
                    "Canonical J2 model is small strain and associative.",
                    "No pressure-sensitive, damage, softening, viscous, or finite-strain model.",
                    "The caller commits trial_state only after global convergence.",
                ),
                operations=(
                    OperationSpec("verify", "Run V00-V11."),
                    OperationSpec(
                        "material_update",
                        "Run one immutable material trial.",
                        ("model", "total_strain", "committed_state", "material"),
                        ("options",),
                        {
                            "model": "combined_1d",
                            "total_strain": 0.002,
                            "committed_state": {
                                "plastic_strain": 0.0,
                                "alpha": 0.0,
                                "backstress": 0.0,
                            },
                            "material": {
                                "E": 210000.0,
                                "sigma_y0": 250.0,
                                "H_iso": 1000.0,
                                "H_kin": 0.0,
                            },
                        },
                    ),
                ),
            ),
            handlers={
                "verify": _constitutive_verify,
                "material_update": _constitutive_material_update,
            },
        ),
        CoreAdapter(
            metadata=CoreMetadata(
                core_id="general_nonlinear_shell",
                title="General Nonlinear Shell",
                version="0.2.0",
                source_path=(
                    "General Nonlinear Shell/4_General-Nonlinear-Shell_16-24周/08_Python数学核心"
                ),
                scope=(
                    "Verification-oriented L0 shell kinematics, loads, material/state, "
                    "section, and continuation primitives"
                ),
                residual_convention="r=f_ext-f_int; K_t=d(f_int)/dq-d(f_ext)/dq; K_t*dq=r",
                state_protocol=(
                    "Global iterations create trial state; commit only after convergence; "
                    "rejected trials roll back."
                ),
                verification_ids=tuple(f"V{index:02d}" for index in range(15)),
                verification_meaning=(
                    "VERIFIED/PARTIAL/REFERENCE_ONLY/NOT_RUN/AUDIT_RESULT/FAILED are "
                    "preserved exactly."
                ),
                limitations=(
                    "L0 primitives are not a production nonlinear shell element.",
                    "Follower-load tangents may be nonsymmetric.",
                    "No current G0-G7 stage gate is claimed passed.",
                ),
                operations=(
                    OperationSpec("verify", "Run V00-V14 and preserve boundary statuses."),
                    OperationSpec(
                        "rotation_update",
                        "Apply a spatial-left or material-right SO(3) increment.",
                        ("current_rotation", "increment"),
                        ("increment_type",),
                        {
                            "current_rotation": [
                                [1.0, 0.0, 0.0],
                                [0.0, 1.0, 0.0],
                                [0.0, 0.0, 1.0],
                            ],
                            "increment": [0.0, 0.0, 0.1],
                            "increment_type": "spatial",
                        },
                    ),
                    OperationSpec(
                        "material_update",
                        "Run the immutable 1D bilinear material primitive.",
                        ("total_strain", "committed_state", "material"),
                        example_parameters={
                            "total_strain": 0.002,
                            "committed_state": {
                                "plastic_strain": 0.0,
                                "accumulated_plastic_strain": 0.0,
                                "stress": 0.0,
                            },
                            "material": {
                                "elastic_modulus": 210000.0,
                                "hardening_modulus": 1000.0,
                                "yield_stress": 250.0,
                            },
                        },
                    ),
                    OperationSpec(
                        "follower_line_load",
                        "Return configuration-dependent force and load tangent.",
                        ("x1", "x2", "pressure"),
                        example_parameters={
                            "x1": [0.0, 0.0],
                            "x2": [2.0, 0.0],
                            "pressure": 5.0,
                        },
                    ),
                    OperationSpec(
                        "plane_stress_condensation",
                        "Apply a Schur complement after the local constraint.",
                        (
                            "active_active",
                            "active_thickness",
                            "thickness_active",
                            "thickness_thickness",
                        ),
                        example_parameters={
                            "active_active": [[12.0, 3.0], [3.0, 10.0]],
                            "active_thickness": [[2.0], [1.0]],
                            "thickness_active": [[2.0, 1.0]],
                            "thickness_thickness": [[8.0]],
                        },
                    ),
                    OperationSpec(
                        "arc_length_step",
                        "Run the scalar reference arc-length step.",
                        ("q_n", "load_factor_n", "arc_length"),
                        (
                            "beta",
                            "reference_load",
                            "direction",
                            "tolerance",
                            "max_iterations",
                        ),
                        {
                            "q_n": 0.0,
                            "load_factor_n": 0.0,
                            "arc_length": 0.1,
                        },
                    ),
                ),
            ),
            handlers={
                "verify": _general_verify,
                "rotation_update": _general_rotation,
                "material_update": _general_material_update,
                "follower_line_load": _general_follower_load,
                "plane_stress_condensation": _general_plane_stress,
                "arc_length_step": _general_arc_length,
            },
        ),
    ]
    return {adapter.metadata.core_id: adapter for adapter in adapters}
