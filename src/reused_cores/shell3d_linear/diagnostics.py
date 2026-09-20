"""Structured diagnostics required by ADR-009 and the P0 code catalog."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal

Severity = Literal["error", "warning", "info"]
EntityType = Literal[
    "document",
    "node",
    "material",
    "section",
    "element",
    "load",
    "constraint",
    "analysis_options",
    "solver",
    "postprocess",
]

_SEVERITY_LETTER: Final = {"E": "error", "W": "warning", "I": "info"}


@dataclass(frozen=True, slots=True)
class DiagnosticLocation:
    entity_type: EntityType
    entity_id: str | None
    json_path: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "json_path": self.json_path,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> DiagnosticLocation:
        return cls(
            entity_type=data["entity_type"],
            entity_id=data["entity_id"],
            json_path=data["json_path"],
        )


@dataclass(frozen=True, slots=True)
class Diagnostic:
    code: str
    severity: Severity
    message: str
    location: DiagnosticLocation
    observed: Any
    threshold: Any
    unit: str | None
    suggested_action: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "location": self.location.to_dict(),
            "observed": self.observed,
            "threshold": self.threshold,
            "unit": self.unit,
            "suggested_action": self.suggested_action,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Diagnostic:
        return cls(
            code=data["code"],
            severity=data["severity"],
            message=data["message"],
            location=DiagnosticLocation.from_dict(data["location"]),
            observed=data["observed"],
            threshold=data["threshold"],
            unit=data["unit"],
            suggested_action=data["suggested_action"],
        )


@dataclass(frozen=True, slots=True)
class DiagnosticSpec:
    severity: Severity
    message: str
    suggested_action: str


DIAGNOSTIC_CATALOG: Final[dict[str, DiagnosticSpec]] = {
    "SHELL-SCHEMA-E001": DiagnosticSpec(
        "error",
        "Schema version, field, type or JSON structure is not supported by contract 1.0.0.",
        "Correct the document to contract 1.0.0. Do not add UI fields.",
    ),
    "SHELL-UNIT-E001": DiagnosticSpec(
        "error",
        "Units are missing, not explicit SI, or have unclear dimensional meaning.",
        "Provide every units field with the frozen SI constants. The core does not convert units.",
    ),
    "SHELL-ID-E001": DiagnosticSpec(
        "error",
        "An identifier is duplicated inside one entity collection.",
        "Give each entity in a collection a unique case-sensitive ID.",
    ),
    "SHELL-REF-E001": DiagnosticSpec(
        "error",
        "A node, material, section or load target reference does not exist.",
        "Point every reference at an ID that exists in the corresponding input array.",
    ),
    "SHELL-NUM-E001": DiagnosticSpec(
        "error",
        "A numeric value is not a finite IEEE-754 binary64 number.",
        "Replace NaN or infinite values with finite SI quantities.",
    ),
    "SHELL-MAT-E001": DiagnosticSpec(
        "error",
        "Young's modulus does not satisfy E > 0.",
        "Set young_modulus to a positive value in Pa.",
    ),
    "SHELL-MAT-E002": DiagnosticSpec(
        "error",
        "Poisson's ratio is outside -1 < nu < 0.5.",
        "Set poisson_ratio strictly between -1 and 0.5.",
    ),
    "SHELL-SEC-E001": DiagnosticSpec(
        "error",
        "Thickness does not satisfy t > 0.",
        "Set thickness to a positive value in m.",
    ),
    "SHELL-SEC-E002": DiagnosticSpec(
        "error",
        "Shear correction factor does not satisfy k_s > 0.",
        "Set shear_correction_factor to a positive value; the baseline is 5/6.",
    ),
    "SHELL-TOP-E001": DiagnosticSpec(
        "error",
        "A Q4 element does not have four distinct node IDs.",
        "Provide exactly four unique node_ids. The validator will not reorder or drop nodes.",
    ),
    "SHELL-GEO-E001": DiagnosticSpec(
        "error",
        "Q4 geometry is degenerate, non-convex, self-intersecting or has a near-zero edge.",
        "Repair the mesh. Do not silently project, split or reorder the element.",
    ),
    "SHELL-GEO-W001": DiagnosticSpec(
        "warning",
        "Planarity ratio r_warp exceeds the warning threshold but is still below the reject limit.",
        "Review node elevations. Results remain solvable under strict_flat_q4_v1.",
    ),
    "SHELL-GEO-E002": DiagnosticSpec(
        "error",
        "Planarity ratio r_warp exceeds the reject threshold for a flat Q4.",
        "Make the four nodes coplanar or replace the element. Warped Q4 is outside the MVP.",
    ),
    "SHELL-GEO-E003": DiagnosticSpec(
        "error",
        "A 2x2 Gauss point has det(J) <= 0.",
        "Fix node order or element shape so every integration-point Jacobian is positive.",
    ),
    "SHELL-GEO-W002": DiagnosticSpec(
        "warning",
        "Normalized Jacobian or Jacobian ratio is poor but still above the reject limits.",
        "Improve element quality; the model remains solvable with a recorded quality warning.",
    ),
    "SHELL-GEO-E004": DiagnosticSpec(
        "error",
        "Normalized minimum Jacobian Jhat_min is at or below the reject threshold.",
        "Remove the near-degenerate mapping. The core will not continue after silent projection.",
    ),
    "SHELL-GEO-E005": DiagnosticSpec(
        "error",
        "An interior edge is shared with the same direction by adjacent elements.",
        "Reverse one element loop so shared edges run opposite. Nodes are not flipped.",
    ),
    "SHELL-LOAD-E001": DiagnosticSpec(
        "error",
        "A load target, local edge number or vector dimension is invalid.",
        "Use global Cartesian vectors and local_edge in {1,2,3,4}.",
    ),
    "SHELL-BC-W001": DiagnosticSpec(
        "warning",
        "The same node and DOF is constrained more than once with the same value.",
        "Remove the duplicate constraint record. The repeated value is kept once.",
    ),
    "SHELL-BC-E001": DiagnosticSpec(
        "error",
        "The same node and DOF has conflicting prescribed values.",
        "Keep a single value for each constrained global DOF.",
    ),
    "SHELL-OPT-E001": DiagnosticSpec(
        "error",
        "A production run requested a verification-only algorithm switch.",
        "Use production shear/drilling, or set run_purpose=verification.",
    ),
    "SHELL-OPT-I001": DiagnosticSpec(
        "info",
        "This run uses raw_q4_full shear or drilling=none as a diagnostic comparison.",
        "Do not publish the result as a production solution.",
    ),
    "SHELL-SOLVE-E001": DiagnosticSpec(
        "error",
        "The linear solve failed, was singular, or produced a non-finite solution.",
        "Inspect constraints, connectivity and matrix rank before retrying the solve.",
    ),
    "SHELL-SOLVE-E002": DiagnosticSpec(
        "error",
        "Scaled relative backward error exceeds 1e-10.",
        "Inspect scaling, constraints and matrix condition before accepting the solve.",
    ),
    "SHELL-SOLVE-W001": DiagnosticSpec(
        "warning",
        "The condition estimate is at least 1e12.",
        "Report the condition and interpret results cautiously.",
    ),
    "SHELL-VERIFY-E001": DiagnosticSpec(
        "error",
        "A mandatory V00-V06 regression failed.",
        "Do not treat the implementation as verified. P1 does not execute V00-V06.",
    ),
    "SHELL-POST-W001": DiagnosticSpec(
        "warning",
        "A derived nodal result near a singularity may not converge pointwise.",
        "Prefer Gauss-point resultants near point loads, corners, supports or jumps.",
    ),
    "SHELL-POST-I001": DiagnosticSpec(
        "info",
        "The output contains derived extrapolation, averaging or envelope quantities.",
        "Keep derived values separate from raw Gauss-point results.",
    ),
}


def code_severity(code: str) -> Severity:
    try:
        letter = code.split("-")[-1][0]
        return _SEVERITY_LETTER[letter]
    except (IndexError, KeyError) as exc:
        raise ValueError(f"Diagnostic code is not in the frozen catalog form: {code}") from exc


def json_path(parts: list[str | int]) -> str:
    text = "$"
    for part in parts:
        if isinstance(part, int):
            text += f"[{part}]"
        elif part.isidentifier():
            text += f".{part}"
        else:
            text += f"[{part!r}]"
    return text


def make_diagnostic(
    code: str,
    *,
    entity_type: EntityType,
    entity_id: str | None,
    json_path: str,
    observed: Any,
    threshold: Any,
    unit: str | None,
    message: str | None = None,
    suggested_action: str | None = None,
) -> Diagnostic:
    spec = DIAGNOSTIC_CATALOG.get(code)
    if spec is None:
        raise ValueError(f"Unknown diagnostic code {code}. Do not invent codes.")
    severity = code_severity(code)
    if spec.severity != severity:
        raise ValueError(f"Catalog severity for {code} does not match the code letter")
    return Diagnostic(
        code=code,
        severity=severity,
        message=message or spec.message,
        location=DiagnosticLocation(
            entity_type=entity_type,
            entity_id=entity_id,
            json_path=json_path,
        ),
        observed=observed,
        threshold=threshold,
        unit=unit,
        suggested_action=suggested_action or spec.suggested_action,
    )


def sort_diagnostics(items: list[Diagnostic]) -> tuple[Diagnostic, ...]:
    rank = {"error": 0, "warning": 1, "info": 2}
    unique: dict[tuple[Any, ...], Diagnostic] = {}
    for item in items:
        key = (
            item.code,
            item.location.json_path,
            item.location.entity_id,
            _freeze(item.observed),
        )
        unique[key] = item
    return tuple(
        sorted(
            unique.values(),
            key=lambda item: (
                rank[item.severity],
                item.code,
                item.location.json_path,
                item.location.entity_id or "",
            ),
        )
    )


def _freeze(value: Any) -> Any:
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, dict):
        return tuple(sorted((key, _freeze(item)) for key, item in value.items()))
    return value
