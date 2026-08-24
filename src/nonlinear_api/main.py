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

    uvicorn.run("nonlinear_api.main:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()


__all__ = ["app", "run"]
