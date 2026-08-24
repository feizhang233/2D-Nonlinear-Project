"""P10 FastAPI application factory, execution, polling, and cancellation endpoints."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import Body, Depends, FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from nonlinear_api.iam_store import (
    SESSION_TTL_DAYS,
    DuplicateEmailError,
    IdentityStore,
)
from nonlinear_api.meshing import SurfaceMeshError, generate_surface_mesh
from nonlinear_api.middleware import RequestSizeLimitMiddleware
from nonlinear_api.schemas import (
    AnalysisRecord,
    AnalysisRequest,
    ApiErrorCategory,
    ApiErrorDetail,
    ApiErrorResponse,
    ApiLimits,
    AuthUser,
    HealthResponse,
    LoginRequest,
    ModelValidationResponse,
    RegisterRequest,
    SavedModel,
    SavedModelCreate,
    SessionResponse,
    SurfaceMeshRequest,
    SurfaceMeshResponse,
)
from nonlinear_api.service import AnalysisService, ApiProblem
from nonlinear_core import __version__


def _request_json_path(location: Sequence[Any]) -> str:
    parts = list(location)
    if parts and parts[0] in {"body", "path", "query", "header"}:
        parts = parts[1:]
    path = "$"
    for part in parts:
        if isinstance(part, int):
            path += f"[{part}]"
        elif isinstance(part, str) and part.isidentifier():
            path += f".{part}"
        else:
            escaped = str(part).replace("\\", "\\\\").replace("'", "\\'")
            path += f"['{escaped}']"
    return path


def _error_response(status_code: int, error: ApiErrorDetail) -> JSONResponse:
    payload = ApiErrorResponse(error=error)
    return JSONResponse(status_code=status_code, content=payload.model_dump(mode="json"))


def create_app(
    *,
    limits: ApiLimits | None = None,
    service: AnalysisService | None = None,
    identity_store: IdentityStore | None = None,
    cors_origins: Sequence[str] = (),
) -> FastAPI:
    actual_service = service or AnalysisService(limits=limits)
    actual_limits = actual_service.limits
    actual_identity_store = identity_store or IdentityStore()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        actual_service.store.clear()

    app = FastAPI(
        title="Nonlinear Studio API",
        version="1.0.0",
        description=(
            "Bounded local API for validated small-model quasi-static nonlinear analyses, "
            "with synchronous or in-process asynchronous execution. "
            "A converged path is not a stability or branch-switching claim."
        ),
        lifespan=lifespan,
    )
    app.state.analysis_service = actual_service
    app.state.api_limits = actual_limits
    app.add_middleware(
        RequestSizeLimitMiddleware,
        max_request_bytes=actual_limits.max_request_bytes,
    )
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type"],
            allow_credentials=True,
        )

    @app.exception_handler(ApiProblem)
    async def api_problem_handler(_: Request, error: ApiProblem) -> JSONResponse:
        return _error_response(error.status_code, error.error)

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(
        _: Request,
        error: RequestValidationError,
    ) -> JSONResponse:
        errors = error.errors()
        first = errors[0] if errors else {"loc": (), "msg": "request validation failed"}
        detail = ApiErrorDetail(
            category=ApiErrorCategory.INPUT,
            code="REQUEST_VALIDATION_FAILED",
            message="HTTP request failed API schema validation",
            location=_request_json_path(first.get("loc", ())),
            details={
                "errors": [
                    {
                        "code": str(item.get("type", "validation_error")),
                        "message": str(item.get("msg", "invalid value")),
                        "location": _request_json_path(item.get("loc", ())),
                    }
                    for item in errors
                ]
            },
        )
        return _error_response(422, detail)

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, error: Exception) -> JSONResponse:
        detail = ApiErrorDetail(
            category=ApiErrorCategory.SERVER,
            code="INTERNAL_SERVER_ERROR",
            message="the API encountered an unexpected server error",
            details={"exception_type": type(error).__name__},
        )
        return _error_response(500, detail)

    error_responses = {
        413: {"model": ApiErrorResponse},
        422: {"model": ApiErrorResponse},
        500: {"model": ApiErrorResponse},
    }

    session_cookie = "nonlinear_studio_session"

    def cookie_secure(request: Request) -> bool:
        configured = os.environ.get("NONLINEAR_COOKIE_SECURE", "").strip().lower()
        if configured:
            return configured in {"1", "true", "yes", "on"}
        return request.url.scheme == "https"

    def set_session_cookie(response: Response, request: Request, token: str) -> None:
        response.set_cookie(
            key=session_cookie,
            value=token,
            max_age=SESSION_TTL_DAYS * 24 * 60 * 60,
            httponly=True,
            secure=cookie_secure(request),
            samesite="lax",
            path="/",
        )

    def optional_user(request: Request) -> dict[str, str] | None:
        token = request.cookies.get(session_cookie)
        return actual_identity_store.user_for_session(token) if token else None

    def require_user(request: Request) -> dict[str, str]:
        user = optional_user(request)
        if user is None:
            raise ApiProblem(
                status_code=401,
                error=ApiErrorDetail(
                    category=ApiErrorCategory.AUTH,
                    code="AUTH_REQUIRED",
                    message="Sign in to save and access model history",
                ),
            )
        return user

    authenticated_user = Depends(require_user)

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    def health() -> HealthResponse:
        return HealthResponse(core_version=__version__, limits=actual_limits)

    @app.get(
        "/api/v1/auth/session",
        response_model=SessionResponse,
        tags=["iam"],
    )
    def current_session(request: Request) -> SessionResponse:
        user = optional_user(request)
        return SessionResponse(authenticated=user is not None, user=user)

    @app.post(
        "/api/v1/auth/register",
        response_model=SessionResponse,
        status_code=201,
        responses={409: {"model": ApiErrorResponse}, **error_responses},
        tags=["iam"],
    )
    def register_account(
        payload: RegisterRequest,
        request: Request,
        response: Response,
    ) -> SessionResponse:
        try:
            user = actual_identity_store.register(
                payload.email,
                payload.display_name,
                payload.password,
            )
        except DuplicateEmailError as error:
            raise ApiProblem(
                status_code=409,
                error=ApiErrorDetail(
                    category=ApiErrorCategory.AUTH,
                    code="EMAIL_ALREADY_REGISTERED",
                    message=str(error),
                    location="$.email",
                ),
            ) from error
        token = actual_identity_store.create_session(user["id"])
        set_session_cookie(response, request, token)
        return SessionResponse(authenticated=True, user=AuthUser.model_validate(user))

    @app.post(
        "/api/v1/auth/login",
        response_model=SessionResponse,
        responses={401: {"model": ApiErrorResponse}, **error_responses},
        tags=["iam"],
    )
    def login_account(
        payload: LoginRequest,
        request: Request,
        response: Response,
    ) -> SessionResponse:
        user = actual_identity_store.authenticate(payload.email, payload.password)
        if user is None:
            raise ApiProblem(
                status_code=401,
                error=ApiErrorDetail(
                    category=ApiErrorCategory.AUTH,
                    code="INVALID_CREDENTIALS",
                    message="Invalid email or password",
                ),
            )
        token = actual_identity_store.create_session(user["id"])
        set_session_cookie(response, request, token)
        return SessionResponse(authenticated=True, user=AuthUser.model_validate(user))

    @app.post(
        "/api/v1/auth/logout",
        status_code=204,
        tags=["iam"],
    )
    def logout_account(request: Request, response: Response) -> Response:
        token = request.cookies.get(session_cookie)
        if token:
            actual_identity_store.delete_session(token)
        response.delete_cookie(key=session_cookie, path="/")
        response.status_code = 204
        return response

    @app.get(
        "/api/v1/models",
        response_model=list[SavedModel],
        responses={401: {"model": ApiErrorResponse}, **error_responses},
        tags=["model history"],
    )
    def list_saved_models(user: dict[str, str] = authenticated_user) -> list[dict[str, Any]]:
        return actual_identity_store.list_models(user["id"])

    @app.post(
        "/api/v1/models",
        response_model=SavedModel,
        status_code=201,
        responses={401: {"model": ApiErrorResponse}, **error_responses},
        tags=["model history"],
    )
    def save_model(
        payload: SavedModelCreate,
        user: dict[str, str] = authenticated_user,
    ) -> dict[str, Any]:
        return actual_identity_store.save_model(
            user["id"],
            payload.name,
            payload.model.model_dump(mode="json"),
        )

    @app.delete(
        "/api/v1/models/{entry_id}",
        status_code=204,
        responses={
            401: {"model": ApiErrorResponse},
            404: {"model": ApiErrorResponse},
            **error_responses,
        },
        tags=["model history"],
    )
    def delete_saved_model(
        entry_id: str,
        user: dict[str, str] = authenticated_user,
    ) -> Response:
        if not actual_identity_store.delete_model(user["id"], entry_id):
            raise ApiProblem(
                status_code=404,
                error=ApiErrorDetail(
                    category=ApiErrorCategory.INPUT,
                    code="SAVED_MODEL_NOT_FOUND",
                    message="Saved model not found",
                ),
            )
        return Response(status_code=204)

    @app.post(
        "/api/v1/models/validate",
        response_model=ModelValidationResponse,
        responses=error_responses,
        tags=["models"],
    )
    def validate_model(
        document: Annotated[dict[str, Any], Body()],
    ) -> ModelValidationResponse:
        return actual_service.validate_model(document)

    @app.post(
        "/api/v1/meshes",
        response_model=SurfaceMeshResponse,
        responses=error_responses,
        tags=["models"],
    )
    def create_surface_mesh(payload: SurfaceMeshRequest) -> SurfaceMeshResponse:
        try:
            return generate_surface_mesh(payload)
        except SurfaceMeshError as error:
            raise ApiProblem(
                status_code=422,
                error=ApiErrorDetail(
                    category=ApiErrorCategory.INPUT,
                    code="GMSH_MESH_INVALID",
                    message=str(error),
                    location="$.model",
                    details={"engine": "Gmsh"},
                ),
            ) from error

    @app.post(
        "/api/v1/analyses",
        response_model=AnalysisRecord,
        status_code=201,
        responses=error_responses,
        tags=["analyses"],
    )
    async def create_analysis(
        payload: AnalysisRequest,
    ) -> AnalysisRecord:
        return await actual_service.submit(payload)

    @app.get(
        "/api/v1/analyses/{analysis_id}",
        response_model=AnalysisRecord,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        tags=["analyses"],
    )
    def get_analysis(analysis_id: UUID) -> AnalysisRecord:
        return actual_service.get(analysis_id)

    @app.delete(
        "/api/v1/analyses/{analysis_id}",
        response_model=AnalysisRecord,
        responses={
            404: {"model": ApiErrorResponse},
            422: {"model": ApiErrorResponse},
            500: {"model": ApiErrorResponse},
        },
        tags=["analyses"],
    )
    def cancel_analysis(analysis_id: UUID) -> AnalysisRecord:
        actual_service.get(analysis_id)
        return actual_service.mark_cancelled(analysis_id)

    return app


__all__ = ["create_app"]
