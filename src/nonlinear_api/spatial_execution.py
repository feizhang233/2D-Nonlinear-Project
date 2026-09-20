"""Shared resource and error boundary for synchronous spatial analyses.

Each route owns its semaphore and numerical operation. The boundary does not
couple one family to another or alter any mathematical-core implementation.
"""

from collections.abc import Callable
from dataclasses import dataclass
from threading import BoundedSemaphore
from typing import TypeVar

import numpy as np
from fastapi import Request

from nonlinear_api.errors import ApiProblem
from nonlinear_api.schemas import ApiErrorCategory, ApiErrorDetail, ApiErrorResponse

T = TypeVar("T")
SPATIAL_ERROR_RESPONSES = {status: {"model": ApiErrorResponse} for status in (413, 422, 429, 500)}


def spatial_problem(code: str, message: str, status: int = 422) -> ApiProblem:
    return ApiProblem(
        status,
        ApiErrorDetail(category=ApiErrorCategory.INPUT, code=code, message=message),
    )


@dataclass(frozen=True)
class SpatialExecution:
    code: str
    label: str
    dofs_per_node: int
    max_elements: int
    max_dofs: int = 600

    def max_nodes(self, request: Request) -> int:
        return min(self.max_dofs, request.app.state.api_limits.max_dofs) // self.dofs_per_node

    def execute(
        self,
        request: Request,
        *,
        node_count: int,
        element_count: int,
        slot: BoundedSemaphore,
        operation: Callable[[], T],
    ) -> T:
        if node_count > self.max_nodes(request) or element_count > self.max_elements:
            raise spatial_problem(
                f"{self.code}_MODEL_LIMIT",
                f"{self.label} supports at most {self.max_nodes(request)} nodes "
                f"and {self.max_elements} elements in this service.",
                413,
            )
        if not slot.acquire(blocking=False):
            raise spatial_problem(
                f"{self.code}_BUSY",
                f"A {self.label} analysis is running. Retry when it finishes.",
                429,
            )
        try:
            return operation()
        except (
            ValueError,
            TypeError,
            np.linalg.LinAlgError,
            FloatingPointError,
            OverflowError,
        ) as e:
            raise spatial_problem(f"{self.code}_INVALID_MODEL", str(e)) from e
        finally:
            slot.release()
