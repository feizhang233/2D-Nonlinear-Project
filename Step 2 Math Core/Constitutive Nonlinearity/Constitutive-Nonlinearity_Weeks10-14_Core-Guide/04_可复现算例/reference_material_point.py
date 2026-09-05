#!/usr/bin/env python3
"""Independent material-point reference for the Weeks 10-14 guide.

The implementation intentionally uses full 3x3 tensors for J2 plasticity so
that engineering-shear Voigt factors cannot be hidden in the reference values.
It writes no files. Run it from any directory with NumPy available.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any

import numpy as np


TENSOR_CONVENTION = "true_tensor_3x3_frobenius"
SCALAR_CONVENTION = "scalar_1d"


@dataclass(frozen=True)
class J2Parameters:
    E: float
    nu: float
    sigma_y0: float
    H_iso: float


@dataclass(frozen=True)
class VoceJ2Parameters:
    E: float
    nu: float
    sigma_y0: float
    Q: float
    b: float
    H_linear: float


@dataclass(frozen=True)
class J2State:
    plastic_strain: np.ndarray
    alpha: float


@dataclass(frozen=True)
class Combined1DParameters:
    E: float
    sigma_y0: float
    H_iso: float
    H_kin: float


@dataclass(frozen=True)
class Combined1DState:
    plastic_strain: float
    alpha: float
    backstress: float


def virgin_j2_state() -> J2State:
    return J2State(np.zeros((3, 3), dtype=float), 0.0)


def virgin_1d_state() -> Combined1DState:
    return Combined1DState(0.0, 0.0, 0.0)


def _elastic_operators(
    parameters: J2Parameters | VoceJ2Parameters,
) -> tuple[float, float, np.ndarray, np.ndarray]:
    E, nu = parameters.E, parameters.nu
    if not (E > 0.0 and -1.0 < nu < 0.5):
        raise ValueError("Require E > 0 and -1 < nu < 0.5")
    shear = E / (2.0 * (1.0 + nu))
    bulk = E / (3.0 * (1.0 - 2.0 * nu))
    identity = np.eye(3)
    symmetric_identity = 0.5 * (
        np.einsum("ik,jl->ijkl", identity, identity)
        + np.einsum("il,jk->ijkl", identity, identity)
    )
    volumetric = np.einsum("ij,kl->ijkl", identity, identity) / 3.0
    deviatoric_identity = symmetric_identity - volumetric
    elastic_tangent = (
        bulk * np.einsum("ij,kl->ijkl", identity, identity)
        + 2.0 * shear * deviatoric_identity
    )
    return shear, bulk, deviatoric_identity, elastic_tangent


def _double_contract(tangent: np.ndarray, strain: np.ndarray) -> np.ndarray:
    return np.einsum("ijkl,kl->ij", tangent, strain)


def _deviator(tensor: np.ndarray) -> np.ndarray:
    return tensor - np.trace(tensor) * np.eye(3) / 3.0


def _validate_j2_inputs(
    total_strain: np.ndarray, committed: J2State
) -> tuple[np.ndarray, np.ndarray]:
    strain = np.asarray(total_strain, dtype=float)
    plastic_strain_n = np.asarray(committed.plastic_strain, dtype=float)
    if strain.shape != (3, 3) or plastic_strain_n.shape != (3, 3):
        raise ValueError("J2 strain and plastic strain must be 3x3 tensors")
    if not np.all(np.isfinite(strain)) or not np.all(np.isfinite(plastic_strain_n)):
        raise ValueError("J2 strain tensors must contain only finite values")
    if not np.allclose(strain, strain.T, atol=1.0e-14):
        raise ValueError("Total strain tensor must be symmetric")
    if not np.allclose(plastic_strain_n, plastic_strain_n.T, atol=1.0e-14):
        raise ValueError("Committed plastic strain tensor must be symmetric")
    if not math.isfinite(committed.alpha) or committed.alpha < 0.0:
        raise ValueError("Committed alpha must be finite and non-negative")
    return strain, plastic_strain_n


def j2_update(
    total_strain: np.ndarray,
    committed: J2State,
    parameters: J2Parameters,
    yield_tolerance: float = 1.0e-10,
) -> tuple[np.ndarray, np.ndarray, J2State, dict[str, Any]]:
    """Small-strain associative J2 update with linear isotropic hardening."""
    strain, plastic_strain_n = _validate_j2_inputs(total_strain, committed)
    if parameters.sigma_y0 <= 0.0 or parameters.H_iso < 0.0:
        raise ValueError("Require sigma_y0 > 0 and H_iso >= 0")

    shear, bulk, deviatoric_identity, elastic_tangent = _elastic_operators(parameters)
    stress_trial = _double_contract(elastic_tangent, strain - plastic_strain_n)
    pressure_trial = np.trace(stress_trial) / 3.0
    deviator_trial = _deviator(stress_trial)
    q_trial = math.sqrt(max(0.0, 1.5 * float(np.tensordot(deviator_trial, deviator_trial))))
    radius_n = parameters.sigma_y0 + parameters.H_iso * committed.alpha
    f_trial = q_trial - radius_n

    if f_trial <= yield_tolerance:
        candidate = J2State(plastic_strain_n.copy(), float(committed.alpha))
        diagnostics = {
            "branch": "elastic",
            "f_trial": f_trial,
            "delta_gamma": 0.0,
            "yield_residual": min(f_trial, 0.0),
            "local_iterations": 0,
            "local_converged": True,
            "tangent_kind": "elastic",
            "convention": TENSOR_CONVENTION,
        }
        return stress_trial, elastic_tangent, candidate, diagnostics

    if q_trial <= 0.0:
        raise FloatingPointError("Plastic branch reached with non-positive q_trial")
    delta_gamma = f_trial / (3.0 * shear + parameters.H_iso)
    normal_trial = 1.5 * deviator_trial / q_trial
    plastic_strain = plastic_strain_n + delta_gamma * normal_trial
    alpha = committed.alpha + delta_gamma
    radial_factor = 1.0 - 3.0 * shear * delta_gamma / q_trial
    deviator = radial_factor * deviator_trial
    stress = pressure_trial * np.eye(3) + deviator
    q = math.sqrt(max(0.0, 1.5 * float(np.tensordot(deviator, deviator))))
    yield_residual = q - (parameters.sigma_y0 + parameters.H_iso * alpha)
    if delta_gamma < 0.0 or radial_factor < -1.0e-12:
        raise FloatingPointError("Invalid J2 plastic multiplier or radial factor")
    if abs(yield_residual) > 1.0e-8 * max(1.0, parameters.sigma_y0):
        raise FloatingPointError(f"J2 return missed the yield surface: {yield_residual}")

    normal_outer = np.einsum("ij,kl->ijkl", normal_trial, normal_trial)
    algorithmic_tangent = (
        bulk * np.einsum("ij,kl->ijkl", np.eye(3), np.eye(3))
        + 2.0 * shear * radial_factor * deviatoric_identity
        - 4.0
        * shear**2
        * (1.0 / (3.0 * shear + parameters.H_iso) - delta_gamma / q_trial)
        * normal_outer
    )
    candidate = J2State(plastic_strain.copy(), float(alpha))
    diagnostics = {
        "branch": "plastic",
        "f_trial": f_trial,
        "delta_gamma": delta_gamma,
        "yield_residual": yield_residual,
        "local_iterations": 0,
        "local_converged": True,
        "tangent_kind": "algorithmic_consistent",
        "convention": TENSOR_CONVENTION,
    }
    return stress, algorithmic_tangent, candidate, diagnostics


def j2_voce_update(
    total_strain: np.ndarray,
    committed: J2State,
    parameters: VoceJ2Parameters,
    local_tolerance: float = 1.0e-12,
    max_iterations: int = 30,
) -> tuple[np.ndarray, np.ndarray, J2State, dict[str, Any]]:
    """J2 update with R(alpha)=Q(1-exp(-b alpha))+H_linear alpha."""
    if parameters.Q < 0.0 or parameters.b < 0.0 or parameters.H_linear < 0.0:
        raise ValueError("Voce parameters must be non-negative")
    strain, plastic_strain_n = _validate_j2_inputs(total_strain, committed)
    if parameters.sigma_y0 <= 0.0:
        raise ValueError("Require sigma_y0 > 0")
    shear, bulk, deviatoric_identity, elastic_tangent = _elastic_operators(parameters)

    def hardening(alpha: float) -> float:
        return parameters.Q * (1.0 - math.exp(-parameters.b * alpha)) + (
            parameters.H_linear * alpha
        )

    def hardening_slope(alpha: float) -> float:
        return (
            parameters.Q * parameters.b * math.exp(-parameters.b * alpha)
            + parameters.H_linear
        )

    stress_trial = _double_contract(elastic_tangent, strain - plastic_strain_n)
    pressure_trial = np.trace(stress_trial) / 3.0
    deviator_trial = _deviator(stress_trial)
    q_trial = math.sqrt(max(0.0, 1.5 * float(np.tensordot(deviator_trial, deviator_trial))))
    f_trial = q_trial - (parameters.sigma_y0 + hardening(committed.alpha))
    if f_trial <= 1.0e-10:
        return (
            stress_trial,
            elastic_tangent,
            J2State(plastic_strain_n.copy(), committed.alpha),
            {
                "branch": "elastic",
                "f_trial": f_trial,
                "delta_gamma": 0.0,
                "yield_residual": min(f_trial, 0.0),
                "local_iterations": 0,
                "local_converged": True,
                "tangent_kind": "elastic",
                "convention": TENSOR_CONVENTION,
            },
        )

    if q_trial <= 0.0:
        raise FloatingPointError("Plastic Voce branch reached with non-positive q_trial")
    low = 0.0
    high = f_trial / (3.0 * shear + parameters.H_linear)
    delta_gamma = min(
        high,
        f_trial / (3.0 * shear + hardening_slope(committed.alpha)),
    )
    converged = False
    iterations = 0
    for iterations in range(1, max_iterations + 1):
        alpha = committed.alpha + delta_gamma
        residual = (
            q_trial
            - 3.0 * shear * delta_gamma
            - parameters.sigma_y0
            - hardening(alpha)
        )
        if abs(residual) <= local_tolerance * max(1.0, parameters.sigma_y0):
            converged = True
            break
        if residual > 0.0:
            low = delta_gamma
        else:
            high = delta_gamma
        derivative = -3.0 * shear - hardening_slope(alpha)
        newton = delta_gamma - residual / derivative
        if not (low < newton < high):
            newton = 0.5 * (low + high)
        delta_gamma = newton
    if not converged:
        raise RuntimeError("Voce local return did not converge")

    alpha = committed.alpha + delta_gamma
    normal_trial = 1.5 * deviator_trial / q_trial
    plastic_strain = plastic_strain_n + delta_gamma * normal_trial
    radial_factor = 1.0 - 3.0 * shear * delta_gamma / q_trial
    deviator = radial_factor * deviator_trial
    stress = pressure_trial * np.eye(3) + deviator
    q = math.sqrt(max(0.0, 1.5 * float(np.tensordot(deviator, deviator))))
    yield_residual = q - (parameters.sigma_y0 + hardening(alpha))
    hardening_alg = hardening_slope(alpha)
    normal_outer = np.einsum("ij,kl->ijkl", normal_trial, normal_trial)
    algorithmic_tangent = (
        bulk * np.einsum("ij,kl->ijkl", np.eye(3), np.eye(3))
        + 2.0 * shear * radial_factor * deviatoric_identity
        - 4.0
        * shear**2
        * (1.0 / (3.0 * shear + hardening_alg) - delta_gamma / q_trial)
        * normal_outer
    )
    return (
        stress,
        algorithmic_tangent,
        J2State(plastic_strain.copy(), alpha),
        {
            "branch": "plastic",
            "f_trial": f_trial,
            "delta_gamma": delta_gamma,
            "yield_residual": yield_residual,
            "local_iterations": iterations,
            "local_converged": True,
            "hardening_slope": hardening_alg,
            "tangent_kind": "algorithmic_consistent",
            "convention": TENSOR_CONVENTION,
        },
    )


def combined_1d_update(
    total_strain: float,
    committed: Combined1DState,
    parameters: Combined1DParameters,
    yield_tolerance: float = 1.0e-12,
) -> tuple[float, float, Combined1DState, dict[str, Any]]:
    """One-dimensional backward-Euler return with linear combined hardening."""
    E = parameters.E
    if E <= 0.0 or parameters.sigma_y0 <= 0.0:
        raise ValueError("Require E > 0 and sigma_y0 > 0")
    if parameters.H_iso < 0.0 or parameters.H_kin < 0.0:
        raise ValueError("Hardening moduli must be non-negative")
    stress_trial = E * (total_strain - committed.plastic_strain)
    shifted_trial = stress_trial - committed.backstress
    f_trial = abs(shifted_trial) - (
        parameters.sigma_y0 + parameters.H_iso * committed.alpha
    )
    if f_trial <= yield_tolerance:
        return (
            stress_trial,
            E,
            Combined1DState(
                committed.plastic_strain,
                committed.alpha,
                committed.backstress,
            ),
            {
                "branch": "elastic",
                "f_trial": f_trial,
                "delta_gamma": 0.0,
                "yield_residual": min(f_trial, 0.0),
                "local_iterations": 0,
                "local_converged": True,
                "tangent_kind": "elastic",
                "convention": SCALAR_CONVENTION,
            },
        )

    direction = 1.0 if shifted_trial >= 0.0 else -1.0
    denominator = E + parameters.H_iso + parameters.H_kin
    delta_gamma = f_trial / denominator
    plastic_strain = committed.plastic_strain + delta_gamma * direction
    alpha = committed.alpha + delta_gamma
    backstress = committed.backstress + parameters.H_kin * delta_gamma * direction
    stress = stress_trial - E * delta_gamma * direction
    yield_residual = abs(stress - backstress) - (
        parameters.sigma_y0 + parameters.H_iso * alpha
    )
    tangent = E * (parameters.H_iso + parameters.H_kin) / denominator
    return (
        stress,
        tangent,
        Combined1DState(plastic_strain, alpha, backstress),
        {
            "branch": "plastic",
            "f_trial": f_trial,
            "delta_gamma": delta_gamma,
            "yield_residual": yield_residual,
            "direction": direction,
            "local_iterations": 0,
            "local_converged": True,
            "tangent_kind": "algorithmic_consistent",
            "convention": SCALAR_CONVENTION,
        },
    )


def condense_plane_stress_tangent(tangent_3d: np.ndarray) -> np.ndarray:
    """Return the in-plane 2x2x2x2 Schur complement for sigma_zz=0.

    The input and output both use true-tensor shear components. The xz and yz
    components are absent because the reference problem constrains them to zero.
    """
    tangent = np.asarray(tangent_3d, dtype=float)
    if tangent.shape != (3, 3, 3, 3):
        raise ValueError("tangent_3d must have shape (3, 3, 3, 3)")
    c_zzzz = float(tangent[2, 2, 2, 2])
    if not math.isfinite(c_zzzz) or abs(c_zzzz) < 1.0e-14:
        raise RuntimeError("Cannot condense a singular C_zzzz block")
    return (
        tangent[:2, :2, :2, :2]
        - np.einsum(
            "ij,kl->ijkl",
            tangent[:2, :2, 2, 2],
            tangent[2, 2, :2, :2],
        )
        / c_zzzz
    )


def plane_stress_update(
    in_plane_strain: np.ndarray,
    committed: J2State,
    parameters: J2Parameters,
    local_tolerance: float = 1.0e-10,
    max_iterations: int = 30,
) -> tuple[float, np.ndarray, np.ndarray, J2State, dict[str, Any]]:
    """Solve epsilon_zz so the 3D J2 update satisfies sigma_zz=0."""
    in_plane = np.asarray(in_plane_strain, dtype=float)
    if in_plane.shape != (2, 2) or not np.allclose(in_plane, in_plane.T):
        raise ValueError("in_plane_strain must be a symmetric 2x2 tensor")
    epsilon_zz = -parameters.nu / (1.0 - parameters.nu) * float(np.trace(in_plane))
    last: tuple[np.ndarray, np.ndarray, J2State, dict[str, Any]] | None = None
    for iteration in range(1, max_iterations + 1):
        full_strain = np.zeros((3, 3), dtype=float)
        full_strain[:2, :2] = in_plane
        full_strain[2, 2] = epsilon_zz
        last = j2_update(full_strain, committed, parameters)
        stress, tangent, candidate, diagnostics = last
        residual = float(stress[2, 2])
        if abs(residual) <= local_tolerance:
            out = dict(diagnostics)
            out.update(
                {
                    "plane_stress_iterations": iteration,
                    "plane_stress_converged": True,
                    "sigma_zz_residual": residual,
                    "epsilon_zz": epsilon_zz,
                    "convention": TENSOR_CONVENTION,
                }
            )
            return epsilon_zz, stress, tangent, candidate, out
        derivative = float(tangent[2, 2, 2, 2])
        if not math.isfinite(derivative) or abs(derivative) < 1.0e-14:
            raise RuntimeError("Singular plane-stress local tangent")
        epsilon_zz -= residual / derivative
    raise RuntimeError(f"Plane-stress local solve did not converge; last={last}")


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.floating, np.integer)):
        return value.item()
    if isinstance(value, dict):
        return {key: _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(item) for item in value]
    return value


def _assert_close(actual: Any, expected: Any, tolerance: float, label: str) -> None:
    if not np.allclose(actual, expected, rtol=tolerance, atol=tolerance):
        raise AssertionError(f"{label}: actual={actual!r}, expected={expected!r}")


def _assert_1d_state_equal(
    actual: Combined1DState,
    expected: Combined1DState,
    tolerance: float,
    label: str,
) -> None:
    _assert_close(
        actual.plastic_strain,
        expected.plastic_strain,
        tolerance,
        f"{label}.plastic_strain",
    )
    _assert_close(actual.alpha, expected.alpha, tolerance, f"{label}.alpha")
    _assert_close(actual.backstress, expected.backstress, tolerance, f"{label}.backstress")


def _assert_j2_state_equal(
    actual: J2State,
    expected: J2State,
    tolerance: float,
    label: str,
) -> None:
    _assert_close(
        actual.plastic_strain,
        expected.plastic_strain,
        tolerance,
        f"{label}.plastic_strain",
    )
    _assert_close(actual.alpha, expected.alpha, tolerance, f"{label}.alpha")


def _with_error_ratios(errors: list[dict[str, float]]) -> list[dict[str, float | None]]:
    enriched: list[dict[str, float | None]] = []
    previous: float | None = None
    for item in errors:
        current = item["relative_error"]
        enriched.append(
            {
                "h": item["h"],
                "relative_error": current,
                "previous_error_over_current": None if previous is None else previous / current,
            }
        )
        previous = current
    return enriched


def run_reference_checks() -> dict[str, Any]:
    results: dict[str, Any] = {}

    # V00-V02: one-dimensional elastic/plastic branches and unloading.
    p1 = Combined1DParameters(210000.0, 250.0, 1000.0, 0.0)
    s0 = virgin_1d_state()
    sigma_el, tangent_el, state_el, d_el = combined_1d_update(0.001, s0, p1)
    _assert_close(sigma_el, 210.0, 1.0e-12, "V00 elastic stress")
    _assert_close(tangent_el, p1.E, 1.0e-12, "V00 elastic tangent")
    _assert_1d_state_equal(state_el, s0, 1.0e-12, "V00 state")
    if d_el["branch"] != "elastic":
        raise AssertionError(f"V00 branch: {d_el['branch']}")
    sigma_1, tangent_1, state_1, d_1 = combined_1d_update(0.002, s0, p1)
    sigma_unload, tangent_unload, state_unload, d_unload = combined_1d_update(
        0.001, state_1, p1
    )
    expected_delta_gamma_1 = 170.0 / 211000.0
    _assert_close(sigma_1, 250.80568720379148, 1.0e-12, "V01 stress")
    _assert_close(d_1["delta_gamma"], expected_delta_gamma_1, 1.0e-12, "V01 delta_gamma")
    _assert_close(state_1.plastic_strain, expected_delta_gamma_1, 1.0e-12, "V01 plastic strain")
    _assert_close(state_1.alpha, expected_delta_gamma_1, 1.0e-12, "V01 alpha")
    _assert_close(tangent_1, 995.260663507109, 1.0e-12, "V01 tangent")
    _assert_close(d_1["yield_residual"], 0.0, 1.0e-10, "V01 yield residual")
    _assert_close(sigma_unload, 40.80568720379148, 1.0e-12, "V02 stress")
    _assert_close(tangent_unload, p1.E, 1.0e-12, "V02 tangent")
    _assert_1d_state_equal(state_unload, state_1, 1.0e-12, "V02 state")
    if d_unload["branch"] != "elastic":
        raise AssertionError(f"V02 branch: {d_unload['branch']}")
    _assert_1d_state_equal(s0, virgin_1d_state(), 0.0, "V00-V02 committed virgin state")
    results["V00"] = {
        "stress": sigma_el,
        "tangent": tangent_el,
        "branch": d_el["branch"],
    }
    results["V01"] = {
        "stress": sigma_1,
        "plastic_strain": state_1.plastic_strain,
        "alpha": state_1.alpha,
        "delta_gamma": d_1["delta_gamma"],
        "tangent": tangent_1,
    }
    results["V02"] = {
        "stress_after_unload": sigma_unload,
        "plastic_strain": state_unload.plastic_strain,
        "alpha": state_unload.alpha,
        "tangent": tangent_unload,
        "branch": d_unload["branch"],
    }

    # V03-V05: tensor J2 checks.
    p3 = J2Parameters(210000.0, 0.3, 250.0, 1000.0)
    j0 = virgin_j2_state()
    hydrostatic_strain = 0.001 * np.eye(3)
    sigma_h, _, state_h, d_h = j2_update(hydrostatic_strain, j0, p3)
    _assert_close(sigma_h, 525.0 * np.eye(3), 1.0e-10, "V03 hydrostatic stress")
    _assert_j2_state_equal(state_h, j0, 1.0e-12, "V03 state")
    if d_h["branch"] != "elastic":
        raise AssertionError(f"V03 branch: {d_h['branch']}")
    target = np.diag([0.002, 0.0, 0.0])
    sigma_j2, tangent_j2, state_j2, d_j2 = j2_update(target, j0, p3)
    q_j2 = math.sqrt(1.5 * float(np.tensordot(_deviator(sigma_j2), _deviator(sigma_j2))))
    _assert_close(
        np.diag(sigma_j2),
        [516.8668985140689, 266.5665507429655, 266.5665507429655],
        1.0e-12,
        "V04 stress",
    )
    _assert_close(q_j2, 250.30034777110342, 1.0e-12, "V04 q")
    _assert_close(d_j2["delta_gamma"], 0.00030034777110338293, 1.0e-12, "V04 delta_gamma")
    _assert_close(state_j2.alpha, d_j2["delta_gamma"], 1.0e-12, "V04 alpha")
    _assert_close(d_j2["yield_residual"], 0.0, 1.0e-9, "V04 yield residual")
    _assert_close(np.trace(state_j2.plastic_strain), 0.0, 1.0e-12, "V05 plastic volume")
    if d_j2["delta_gamma"] < 0.0 or p3.sigma_y0 * d_j2["delta_gamma"] < 0.0:
        raise AssertionError("V05 KKT or dissipation sign failed")
    _assert_j2_state_equal(j0, virgin_j2_state(), 0.0, "V03-V05 committed virgin state")
    results["V03"] = {
        "stress_diagonal": np.diag(sigma_h),
        "alpha": state_h.alpha,
        "branch": d_h["branch"],
    }
    results["V04"] = {
        "stress_diagonal": np.diag(sigma_j2),
        "q": q_j2,
        "alpha": state_j2.alpha,
        "delta_gamma": d_j2["delta_gamma"],
    }
    results["V05"] = {
        "plastic_strain_trace": np.trace(state_j2.plastic_strain),
        "yield_residual": d_j2["yield_residual"],
        "ideal_plastic_dissipation_increment": p3.sigma_y0 * d_j2["delta_gamma"],
    }

    # V06: central directional derivative from the same committed state.
    direction = np.array(
        [[0.6, 0.2, 0.0], [0.2, -0.1, 0.0], [0.0, 0.0, 0.3]], dtype=float
    )
    direction /= np.linalg.norm(direction)
    predicted = _double_contract(tangent_j2, direction)
    errors: list[dict[str, float]] = []
    for h in [2.0e-5, 1.0e-5, 5.0e-6, 2.5e-6, 1.25e-6, 6.25e-7]:
        sigma_plus, _, _, d_plus = j2_update(target + h * direction, j0, p3)
        sigma_minus, _, _, d_minus = j2_update(target - h * direction, j0, p3)
        if d_plus["branch"] != "plastic" or d_minus["branch"] != "plastic":
            raise AssertionError("V06 perturbation crossed the plastic branch")
        finite_difference = (sigma_plus - sigma_minus) / (2.0 * h)
        error = float(
            np.linalg.norm(finite_difference - predicted)
            / max(1.0, np.linalg.norm(predicted))
        )
        errors.append({"h": h, "relative_error": error})
    if not (errors[-1]["relative_error"] < 1.0e-6):
        raise AssertionError(f"V06 tangent check failed: {errors}")
    error_table = _with_error_ratios(errors)
    v06_ratios = [
        item["previous_error_over_current"]
        for item in error_table[1:]
    ]
    if not all(ratio is not None and 3.8 <= ratio <= 4.2 for ratio in v06_ratios):
        raise AssertionError(f"V06 did not show second-order convergence: {error_table}")
    results["V06"] = {"directional_derivative_errors": error_table}

    # V07: a rejected trial must not mutate or replace the committed state.
    committed_before = Combined1DState(
        state_1.plastic_strain, state_1.alpha, state_1.backstress
    )
    _rejected = combined_1d_update(0.003, committed_before, p1)
    sigma_after_reject, _, state_after_reject, _ = combined_1d_update(
        0.001, committed_before, p1
    )
    _assert_1d_state_equal(committed_before, state_1, 1.0e-12, "V07 committed state")
    _assert_close(sigma_after_reject, sigma_unload, 1.0e-12, "V07 rejected trial")
    _assert_1d_state_equal(state_after_reject, state_unload, 1.0e-12, "V07 retry state")
    results["V07"] = {
        "committed_unchanged": True,
        "stress_after_rejected_trial": sigma_after_reject,
        "candidate_alpha": state_after_reject.alpha,
    }

    # V08: cyclic combined hardening.
    pc = Combined1DParameters(200000.0, 250.0, 1000.0, 9000.0)
    cyclic_state = virgin_1d_state()
    cyclic_history: list[dict[str, Any]] = []
    cyclic_strain_history = [0.0, 0.002, 0.0, -0.002, 0.0, 0.002]
    for step, strain in enumerate(cyclic_strain_history):
        stress, tangent, cyclic_state, diagnostics = combined_1d_update(
            strain, cyclic_state, pc
        )
        cyclic_history.append(
            {
                "step": step,
                "strain": strain,
                "stress": stress,
                "plastic_strain": cyclic_state.plastic_strain,
                "alpha": cyclic_state.alpha,
                "backstress": cyclic_state.backstress,
                "delta_gamma": diagnostics["delta_gamma"],
                "yield_residual": diagnostics["yield_residual"],
                "branch": diagnostics["branch"],
                "tangent": tangent,
            }
        )
    expected_cyclic_values = np.array(
        [
            [0.0, 0.0, 0.0, 0.0, 0.0, 200000.0],
            [
                257.1428571428571,
                0.0007142857142857143,
                0.0007142857142857143,
                6.428571428571429,
                0.0007142857142857143,
                9523.809523809523,
            ],
            [
                -142.85714285714286,
                0.0007142857142857143,
                0.0007142857142857143,
                6.428571428571429,
                0.0,
                200000.0,
            ],
            [
                -258.5034013605442,
                -0.000707482993197279,
                0.0021360544217687077,
                -6.36734693877551,
                0.0014217687074829933,
                9523.809523809523,
            ],
            [
                141.4965986394558,
                -0.000707482993197279,
                0.0021360544217687077,
                -6.36734693877551,
                0.0,
                200000.0,
            ],
            [
                259.8509880142533,
                0.0007007450599287335,
                0.00354428247489472,
                6.306705539358603,
                0.0014082280531260126,
                9523.809523809523,
            ],
        ]
    )
    actual_cyclic_values = np.array(
        [
            [
                row["stress"],
                row["plastic_strain"],
                row["alpha"],
                row["backstress"],
                row["delta_gamma"],
                row["tangent"],
            ]
            for row in cyclic_history
        ]
    )
    _assert_close(actual_cyclic_values, expected_cyclic_values, 1.0e-10, "V08 history")
    if [row["branch"] for row in cyclic_history] != [
        "elastic", "plastic", "elastic", "plastic", "elastic", "plastic"
    ]:
        raise AssertionError(f"V08 branch history failed: {cyclic_history}")
    if np.any(np.diff([row["alpha"] for row in cyclic_history]) < -1.0e-14):
        raise AssertionError("V08 alpha is not monotone")
    if any(
        abs(row["yield_residual"]) > 1.0e-9
        for row in cyclic_history
        if row["branch"] == "plastic"
    ):
        raise AssertionError("V08 plastic yield residual exceeded tolerance")

    refined_endpoints: list[tuple[float, Combined1DState]] = []
    refined_state = virgin_1d_state()
    refined_stress, _, refined_state, _ = combined_1d_update(
        cyclic_strain_history[0], refined_state, pc
    )
    refined_endpoints.append((refined_stress, refined_state))
    for segment_start, segment_end in zip(
        cyclic_strain_history[:-1], cyclic_strain_history[1:]
    ):
        for refined_strain in np.linspace(segment_start, segment_end, 3)[1:]:
            refined_stress, _, refined_state, _ = combined_1d_update(
                float(refined_strain), refined_state, pc
            )
        refined_endpoints.append((refined_stress, refined_state))

    refinement_differences: list[float] = []
    for coarse_row, (refined_stress, refined_state) in zip(
        cyclic_history, refined_endpoints
    ):
        refinement_differences.extend(
            [
                abs(coarse_row["stress"] - refined_stress),
                abs(coarse_row["plastic_strain"] - refined_state.plastic_strain),
                abs(coarse_row["alpha"] - refined_state.alpha),
                abs(coarse_row["backstress"] - refined_state.backstress),
            ]
        )
    refinement_max_difference = max(refinement_differences)
    if refinement_max_difference > 1.0e-12:
        raise AssertionError(
            f"V08 path refinement failed: {refinement_max_difference}"
        )
    reverse_yield_stress = cyclic_history[1]["backstress"] - (
        pc.sigma_y0 + pc.H_iso * cyclic_history[1]["alpha"]
    )
    reverse_yield_strain = cyclic_history[1]["plastic_strain"] + reverse_yield_stress / pc.E
    _assert_close(reverse_yield_stress, -244.2857142857143, 1.0e-12, "V08 reverse yield stress")
    _assert_close(reverse_yield_strain, -0.0005071428571428572, 1.0e-12, "V08 reverse yield strain")
    results["V08"] = {
        "history": cyclic_history,
        "reverse_yield_stress_after_first_positive_peak": reverse_yield_stress,
        "reverse_yield_strain_after_first_positive_peak": reverse_yield_strain,
        "path_refinement": {
            "substeps_per_segment": 2,
            "maximum_endpoint_difference": refinement_max_difference,
        },
    }

    # V09: local plane-stress constraint.
    ezz, sigma_ps, tangent_ps, state_ps, d_ps = plane_stress_update(
        np.array([[0.002, 0.0], [0.0, 0.0]]), j0, p3
    )
    _assert_close(sigma_ps[2, 2], 0.0, 1.0e-9, "V09 sigma_zz")
    _assert_close(ezz, -0.0012435578687300603, 1.0e-10, "V09 epsilon_zz")
    _assert_close(
        np.diag(sigma_ps),
        [287.0710462143973, 110.06107270232101, 0.0],
        1.0e-10,
        "V09 stress",
    )
    _assert_close(state_ps.alpha, 0.0008542963771601343, 1.0e-10, "V09 alpha")
    if d_ps["plane_stress_iterations"] != 5:
        raise AssertionError(f"V09 iterations: {d_ps['plane_stress_iterations']}")
    czz = tangent_ps[2, 2, 2, 2]
    in_plane_direction = np.array([[0.7, 0.15], [0.15, -0.2]], dtype=float)
    in_plane_direction /= np.linalg.norm(in_plane_direction)
    condensed_tangent = condense_plane_stress_tangent(tangent_ps)
    predicted_plane_stress = _double_contract(condensed_tangent, in_plane_direction)
    plane_stress_errors: list[dict[str, float]] = []
    in_plane_target = np.array([[0.002, 0.0], [0.0, 0.0]])
    for h in [2.0e-5, 1.0e-5, 5.0e-6, 2.5e-6, 1.25e-6]:
        _, sigma_plus, _, _, _ = plane_stress_update(
            in_plane_target + h * in_plane_direction, j0, p3
        )
        _, sigma_minus, _, _, _ = plane_stress_update(
            in_plane_target - h * in_plane_direction, j0, p3
        )
        finite_difference = (sigma_plus[:2, :2] - sigma_minus[:2, :2]) / (2.0 * h)
        error = float(
            np.linalg.norm(finite_difference - predicted_plane_stress)
            / max(1.0, np.linalg.norm(predicted_plane_stress))
        )
        plane_stress_errors.append({"h": h, "relative_error": error})
    if not (plane_stress_errors[-1]["relative_error"] < 1.0e-6):
        raise AssertionError(f"V09 condensed tangent check failed: {plane_stress_errors}")
    plane_stress_error_table = _with_error_ratios(plane_stress_errors)
    v09_ratios = [
        item["previous_error_over_current"]
        for item in plane_stress_error_table[1:]
    ]
    if not all(ratio is not None and 3.8 <= ratio <= 4.2 for ratio in v09_ratios):
        raise AssertionError(
            f"V09 did not show second-order convergence: {plane_stress_error_table}"
        )
    _assert_j2_state_equal(j0, virgin_j2_state(), 0.0, "V09 committed virgin state")
    results["V09"] = {
        "epsilon_zz": ezz,
        "stress_diagonal": np.diag(sigma_ps),
        "alpha": state_ps.alpha,
        "sigma_zz_residual": d_ps["sigma_zz_residual"],
        "plane_stress_iterations": d_ps["plane_stress_iterations"],
        "C_zzzz_3d_at_solution": czz,
        "condensed_directional_derivative_errors": plane_stress_error_table,
    }

    # V10: nonlinear Voce hardening local Newton.
    p10 = VoceJ2Parameters(
        E=210000.0,
        nu=0.3,
        sigma_y0=250.0,
        Q=100.0,
        b=15.0,
        H_linear=500.0,
    )
    sigma_v, _, state_v, d_v = j2_voce_update(
        np.diag([0.003, 0.0, 0.0]),
        j0,
        p10,
    )
    q_v = math.sqrt(1.5 * float(np.tensordot(_deviator(sigma_v), _deviator(sigma_v))))
    _assert_close(d_v["delta_gamma"], 0.0009603697236943074, 1.0e-10, "V10 delta_gamma")
    _assert_close(
        np.diag(sigma_v),
        [692.9402754032272, 441.02986229838626, 441.02986229838626],
        1.0e-10,
        "V10 stress",
    )
    _assert_close(q_v, 251.91041310484098, 1.0e-10, "V10 q")
    _assert_close(d_v["hardening_slope"], 1978.5465763553907, 1.0e-10, "V10 hardening slope")
    if d_v["local_iterations"] != 2 or abs(d_v["yield_residual"]) > 1.0e-8:
        raise AssertionError(f"V10 local Newton failed: {d_v}")
    _assert_j2_state_equal(j0, virgin_j2_state(), 0.0, "V10 committed virgin state")
    results["V10"] = {
        "stress_diagonal": np.diag(sigma_v),
        "q": q_v,
        "alpha": state_v.alpha,
        "delta_gamma": d_v["delta_gamma"],
        "yield_residual": d_v["yield_residual"],
        "local_iterations": d_v["local_iterations"],
        "hardening_slope": d_v["hardening_slope"],
    }

    # V11: one-DOF bar global Newton using the material algorithmic tangent.
    target_stress = 260.0
    strain = 0.0
    newton_history: list[dict[str, float]] = []
    final_candidate = virgin_1d_state()
    for iteration in range(8):
        stress, tangent, final_candidate, _ = combined_1d_update(
            strain, virgin_1d_state(), pc
        )
        residual = target_stress - stress
        newton_history.append(
            {
                "iteration": iteration,
                "strain": strain,
                "stress": stress,
                "residual": residual,
                "tangent": tangent,
            }
        )
        if abs(residual) <= 1.0e-12:
            break
        strain += residual / tangent
    _assert_close(strain, 0.0023, 1.0e-12, "V11 strain")
    _assert_close(final_candidate.plastic_strain, 0.001, 1.0e-12, "V11 plastic strain")
    _assert_close(final_candidate.alpha, 0.001, 1.0e-12, "V11 alpha")
    _assert_close(final_candidate.backstress, 9.0, 1.0e-12, "V11 backstress")
    if len(newton_history) != 3 or abs(newton_history[-1]["residual"]) > 1.0e-12:
        raise AssertionError(f"V11 Newton history failed: {newton_history}")
    results["V11"] = {
        "target_stress": target_stress,
        "history": newton_history,
        "final_state": {
            "plastic_strain": final_candidate.plastic_strain,
            "alpha": final_candidate.alpha,
            "backstress": final_candidate.backstress,
        },
    }

    return results


def main() -> None:
    results = run_reference_checks()
    print("PACKAGE_REFERENCE_CHECK: OK")
    print(json.dumps(_to_jsonable(results), indent=2, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
