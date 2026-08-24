"""Small, solver-agnostic progress and cooperative-cancellation contracts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SolveProgress:
    """The currently evaluated Newton iteration and committed-step count."""

    step_index: int
    iteration_index: int
    accepted_steps: int
    message: str = "nonlinear iteration is running"


ProgressCallback = Callable[[SolveProgress], None]


class SolverCancelled(BaseException):
    """Cooperative stop signal that numerical exception handlers must not absorb."""


def emit_progress(
    callback: ProgressCallback | None,
    *,
    step_index: int,
    iteration_index: int,
    accepted_steps: int,
    message: str = "nonlinear iteration is running",
) -> None:
    if callback is not None:
        callback(
            SolveProgress(
                step_index=step_index,
                iteration_index=iteration_index,
                accepted_steps=accepted_steps,
                message=message,
            )
        )


__all__ = ["ProgressCallback", "SolveProgress", "SolverCancelled", "emit_progress"]
