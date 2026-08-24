"""Versioned P10 HTTP request, status, result, and error contracts."""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator, model_validator

from nonlinear_core import ContractIssue, ModelInput, SolveResult, SolveStatus
from nonlinear_core.model import ElementInput, ModelFamily, NodeInput


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, validate_default=True)


class ApiLimits(ApiModel):
    max_request_bytes: Annotated[int, Field(ge=1024)] = 1_048_576
    max_dofs: Annotated[int, Field(ge=1)] = 10_000


class ExecutionMode(StrEnum):
    SYNCHRONOUS = "synchronous"
    ASYNCHRONOUS = "asynchronous"


class AnalysisStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ApiErrorCategory(StrEnum):
    INPUT = "input"
    COMPUTATION = "computation"
    AUTH = "auth"
    SERVER = "server"


class ApiErrorDetail(ApiModel):
    category: ApiErrorCategory
    code: str
    message: str
    location: str | None = None
    details: dict[str, JsonValue] = Field(default_factory=dict)


class ApiErrorResponse(ApiModel):
    error: ApiErrorDetail


class HealthResponse(ApiModel):
    status: str = "ok"
    service: str = "nonlinear-api"
    api_version: str = "1.0.0"
    core_version: str
    execution_mode: ExecutionMode = ExecutionMode.SYNCHRONOUS
    supported_execution_modes: tuple[ExecutionMode, ...] = (
        ExecutionMode.SYNCHRONOUS,
        ExecutionMode.ASYNCHRONOUS,
    )
    limits: ApiLimits


class RegisterRequest(ApiModel):
    email: Annotated[str, Field(min_length=3, max_length=320)]
    display_name: Annotated[str, Field(min_length=2, max_length=120)]
    password: Annotated[str, Field(min_length=8, max_length=128)]

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        normalized = value.strip().casefold()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
            raise ValueError("enter a valid email address")
        return normalized

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("display name must contain at least 2 characters")
        return normalized


class LoginRequest(ApiModel):
    email: Annotated[str, Field(min_length=3, max_length=320)]
    password: Annotated[str, Field(min_length=1, max_length=128)]


class AuthUser(ApiModel):
    id: str
    email: str
    display_name: str
    created_at: datetime


class SessionResponse(ApiModel):
    authenticated: bool
    user: AuthUser | None = None

    @model_validator(mode="after")
    def check_session_payload(self) -> Self:
        if self.authenticated != (self.user is not None):
            raise ValueError("authenticated must match the user payload")
        return self


class SavedModelCreate(ApiModel):
    name: Annotated[str, Field(min_length=1, max_length=160)]
    model: ModelInput

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("saved model name cannot be empty")
        return normalized


class SavedModel(ApiModel):
    id: str
    name: str
    model_family: ModelFamily
    saved_at: datetime
    model: ModelInput


class ModelValidationResponse(ApiModel):
    valid: bool
    execution_eligible: bool
    model: ModelInput | None = None
    dof_count: int | None = None
    errors: tuple[ContractIssue, ...] = ()
    limit_error: ApiErrorDetail | None = None

    @model_validator(mode="after")
    def check_validation_payload(self) -> Self:
        if self.valid != (self.model is not None and not self.errors):
            raise ValueError("valid must match the model/errors payload")
        if self.execution_eligible and (not self.valid or self.limit_error is not None):
            raise ValueError("execution_eligible requires a valid model within limits")
        if self.valid and self.dof_count is None:
            raise ValueError("valid model responses require dof_count")
        return self


class SurfaceMeshRequest(ApiModel):
    model: ModelInput
    mesh_size: Annotated[float, Field(gt=0.0, allow_inf_nan=False)]


class MeshBoundarySegment(ApiModel):
    element_id: str
    local_edge: Annotated[int, Field(ge=0, le=3)]
    node_ids: tuple[str, str]


class MeshBoundary(ApiModel):
    id: str
    label: str
    node_ids: tuple[str, ...]
    segments: tuple[MeshBoundarySegment, ...]
    length: Annotated[float, Field(gt=0.0, allow_inf_nan=False)]


class SurfaceMeshResponse(ApiModel):
    engine: str = "Gmsh"
    engine_version: str
    model_family: ModelFamily
    formulation: str
    mesh_size: Annotated[float, Field(gt=0.0, allow_inf_nan=False)]
    nodes: tuple[NodeInput, ...]
    elements: tuple[ElementInput, ...]
    boundaries: tuple[MeshBoundary, ...]


class AnalysisRestart(ApiModel):
    restart_schema_version: str = "1.0.0"
    committed_state: dict[str, JsonValue]
    arc_length_increment: dict[str, JsonValue] | None = None

    @model_validator(mode="after")
    def check_version(self) -> Self:
        if self.restart_schema_version != "1.0.0":
            raise ValueError("unsupported analysis restart schema version")
        return self


class AnalysisRequest(ApiModel):
    model: dict[str, Any]
    target_load_factor: Annotated[float, Field(allow_inf_nan=False)] | None = None
    number_of_steps: Annotated[int, Field(ge=1)] | None = None
    execution_mode: ExecutionMode = ExecutionMode.SYNCHRONOUS
    restart: AnalysisRestart | None = None


class AnalysisProgress(ApiModel):
    current_step: Annotated[int, Field(ge=0)] | None = None
    current_iteration: Annotated[int, Field(ge=0)] | None = None
    accepted_steps: Annotated[int, Field(ge=0)] = 0
    message: str = ""


class AnalysisRecord(ApiModel):
    analysis_id: UUID
    status: AnalysisStatus
    execution_mode: ExecutionMode
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    model_id: str
    model_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    control_method: str
    dof_count: Annotated[int, Field(ge=1)]
    progress: AnalysisProgress = Field(default_factory=AnalysisProgress)
    result: SolveResult | None = None
    error: ApiErrorDetail | None = None

    @model_validator(mode="after")
    def check_status_payload(self) -> Self:
        terminal = self.status in {
            AnalysisStatus.SUCCEEDED,
            AnalysisStatus.FAILED,
            AnalysisStatus.CANCELLED,
        }
        if terminal != (self.completed_at is not None):
            raise ValueError("terminal analysis records require completed_at")
        if self.status is AnalysisStatus.QUEUED and self.started_at is not None:
            raise ValueError("queued records cannot have started_at")
        if self.status is not AnalysisStatus.QUEUED and self.started_at is None:
            raise ValueError("started/terminal records require started_at")
        if self.status is AnalysisStatus.SUCCEEDED:
            if self.result is None or self.result.status is not SolveStatus.SUCCEEDED:
                raise ValueError("succeeded analyses require a succeeded SolveResult")
            if self.error is not None:
                raise ValueError("succeeded analyses cannot carry an error")
        elif self.status is AnalysisStatus.FAILED:
            if self.error is None:
                raise ValueError("failed analyses require an error")
            if self.result is not None and self.result.status is not SolveStatus.FAILED:
                raise ValueError("failed analyses may retain only a failed SolveResult")
        elif self.status is AnalysisStatus.CANCELLED:
            if self.result is not None or self.error is None:
                raise ValueError("cancelled analyses require an error and no result")
        elif self.result is not None or self.error is not None:
            raise ValueError("non-terminal analyses cannot carry results or errors")
        return self


__all__ = [
    "AnalysisProgress",
    "AnalysisRecord",
    "AnalysisRequest",
    "AnalysisRestart",
    "AnalysisStatus",
    "ApiErrorCategory",
    "ApiErrorDetail",
    "ApiErrorResponse",
    "ApiLimits",
    "AuthUser",
    "ExecutionMode",
    "HealthResponse",
    "LoginRequest",
    "MeshBoundary",
    "MeshBoundarySegment",
    "ModelValidationResponse",
    "RegisterRequest",
    "SavedModel",
    "SavedModelCreate",
    "SessionResponse",
    "SurfaceMeshRequest",
    "SurfaceMeshResponse",
]
