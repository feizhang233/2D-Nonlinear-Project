"""ASGI request-body limit enforced before Pydantic or solver allocation."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from nonlinear_api.schemas import (
    ApiErrorCategory,
    ApiErrorDetail,
    ApiErrorResponse,
)


class _RequestTooLarge(Exception):
    pass


class RequestSizeLimitMiddleware:
    def __init__(self, app: ASGIApp, *, max_request_bytes: int) -> None:
        self.app = app
        self.max_request_bytes = max_request_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        content_length = headers.get(b"content-length")
        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = 0
            if declared_size > self.max_request_bytes:
                await self._reject(scope, receive, send, declared_size)
                return

        received_size = 0
        response_started = False

        async def limited_receive() -> Message:
            nonlocal received_size
            message = await receive()
            if message["type"] == "http.request":
                received_size += len(message.get("body", b""))
                if received_size > self.max_request_bytes:
                    raise _RequestTooLarge
            return message

        async def tracked_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, limited_receive, tracked_send)
        except _RequestTooLarge:
            if response_started:
                raise
            await self._reject(scope, receive, send, received_size)

    async def _reject(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        actual_size: int,
    ) -> None:
        payload = ApiErrorResponse(
            error=ApiErrorDetail(
                category=ApiErrorCategory.INPUT,
                code="REQUEST_TOO_LARGE",
                message=(
                    f"request body exceeds the {self.max_request_bytes}-byte synchronous API limit"
                ),
                location="$.body",
                details={
                    "actual_or_declared_bytes": actual_size,
                    "max_request_bytes": self.max_request_bytes,
                },
            )
        )
        response = JSONResponse(
            status_code=413,
            content=payload.model_dump(mode="json"),
        )
        await response(scope, receive, send)


__all__ = ["RequestSizeLimitMiddleware"]
