"""P1 output and traceability contracts."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import Field, JsonValue, model_validator

from nonlinear_core.constants import SCHEMA_VERSION
from nonlinear_core.model import (
    ContractModel,
    ControlMethod,
    FiniteFloat,
    Identifier,
    NonEmptyString,
    NonNegativeFloat,
)


class IterationStatus(StrEnum):
    CONTINUE = "continue"
    CONVERGED = "converged"
    REJECTED = "rejected"


class StepStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SolveStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class FailureCode(StrEnum):
    MODEL_ERROR = "MODEL_ERROR"
    CONTROL_ERROR = "CONTROL_ERROR"
    TANGENT_ERROR = "TANGENT_ERROR"
    STATE_ERROR = "STATE_ERROR"
    LINEAR_SOLVE_ERROR = "LINEAR_SOLVE_ERROR"
    LOCAL_MATERIAL_ERROR = "LOCAL_MATERIAL_ERROR"
    NONCONVERGENCE = "NONCONVERGENCE"


class ResultLocation(StrEnum):
    GLOBAL = "global"
    NODE = "node"
    ELEMENT = "element"
    GAUSS_POINT = "gauss_point"


PositiveStep = Annotated[float, Field(gt=0.0, allow_inf_nan=False)]


class IterationRecord(ContractModel):
    step_index: Annotated[int, Field(ge=0)]
    iteration_index: Annotated[int, Field(ge=0)]
    load_factor: FiniteFloat
    residual_norm: NonNegativeFloat
    displacement_correction_norm: NonNegativeFloat
    energy_norm: NonNegativeFloat
    linear_residual_norm: NonNegativeFloat
    accepted_alpha: Annotated[float, Field(gt=0.0, le=1.0, allow_inf_nan=False)] = 1.0
    tangent_reassembled: bool
    status: IterationStatus
    diagnostics: dict[str, JsonValue] = Field(default_factory=dict)


class FailureRecord(ContractModel):
    code: FailureCode
    message: NonEmptyString
    json_path: NonEmptyString | None = None
    step_index: Annotated[int, Field(ge=0)] | None = None
    iteration_index: Annotated[int, Field(ge=0)] | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)


class StepResult(ContractModel):
    step_index: Annotated[int, Field(ge=0)]
    status: StepStatus
    control_method: ControlMethod
    load_factor: FiniteFloat
    requested_step_size: PositiveStep
    accepted_step_size: PositiveStep | None = None
    state_id: NonEmptyString | None = None
    iterations: tuple[IterationRecord, ...] = ()
    failure: FailureRecord | None = None
    response: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_status_payload(self) -> Self:
        if self.status is StepStatus.ACCEPTED:
            if self.accepted_step_size is None or self.state_id is None:
                raise ValueError("accepted steps require accepted_step_size and state_id")
            if self.failure is not None:
                raise ValueError("accepted steps cannot carry a failure record")
        elif self.failure is None:
            raise ValueError("rejected steps require a failure record")
        return self


class ResultField(ContractModel):
    name: NonEmptyString
    location: ResultLocation
    basis: NonEmptyString | None = None
    records: tuple[dict[str, JsonValue], ...]
    is_derived: bool = False
    source: NonEmptyString | None = None

    @model_validator(mode="after")
    def check_derivation_label(self) -> Self:
        if self.is_derived and self.source is None:
            raise ValueError("derived result fields require a source description")
        return self


class PostResult(ContractModel):
    raw_fields: tuple[ResultField, ...] = ()
    derived_fields: tuple[ResultField, ...] = ()
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_raw_and_derived_groups(self) -> Self:
        if any(field.is_derived for field in self.raw_fields):
            raise ValueError("raw_fields cannot contain is_derived=true")
        if any(not field.is_derived for field in self.derived_fields):
            raise ValueError("derived_fields require is_derived=true")
        return self


class SolveResult(ContractModel):
    schema_version: Literal["1.0.0"] = SCHEMA_VERSION
    model_id: Identifier
    model_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    solver_version: NonEmptyString
    status: SolveStatus
    steps: tuple[StepResult, ...] = ()
    failures: tuple[FailureRecord, ...] = ()
    post_result: PostResult | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def check_solve_status(self) -> Self:
        if self.status is SolveStatus.FAILED and not self.failures:
            raise ValueError("failed solve results require at least one failure record")
        return self


__all__ = [
    "FailureCode",
    "FailureRecord",
    "IterationRecord",
    "IterationStatus",
    "PostResult",
    "ResultField",
    "ResultLocation",
    "SolveResult",
    "SolveStatus",
    "StepResult",
    "StepStatus",
]
