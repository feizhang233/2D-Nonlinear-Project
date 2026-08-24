"""Default ASGI application and local P10 server entry point."""

from __future__ import annotations

import os

from nonlinear_api.app import create_app

app = create_app(
    cors_origins=tuple(
        origin.strip()
        for origin in os.getenv("NONLINEAR_CORS_ORIGINS", "").split(",")
        if origin.strip()
    )
)


def run() -> None:
    import uvicorn

    host = os.environ.get("NONLINEAR_HOST", "127.0.0.1")
    port = int(os.environ.get("NONLINEAR_API_PORT", "8000"))
    uvicorn.run("nonlinear_api.main:app", host=host, port=port)


if __name__ == "__main__":
    run()


__all__ = ["app", "run"]
