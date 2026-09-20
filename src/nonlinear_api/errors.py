"""HTTP problem shared by routes and execution services."""

from nonlinear_api.schemas import ApiErrorDetail


class ApiProblem(Exception):
    """One already-classified HTTP problem safe to serialize to the client."""

    def __init__(self, status_code: int, error: ApiErrorDetail) -> None:
        super().__init__(error.message)
        self.status_code = status_code
        self.error = error
