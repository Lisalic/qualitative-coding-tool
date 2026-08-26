"""Shared exception hierarchy for service-layer code.

Services raise these instead of building ``JSONResponse``/``HTTPException``
ad hoc; ``main.py`` registers one handler that maps every ``AppError`` to
the existing ``{"error": "..."}`` wire format, so ``frontend/src/api.js``
needs no changes to keep parsing errors correctly.
"""

class AppError(Exception):
    """Base class for errors a route handler should turn into an HTTP response."""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class NotFoundError(AppError):
    status_code = 404


class ForbiddenError(AppError):
    status_code = 403


class UnauthorizedError(AppError):
    status_code = 401


class ValidationAppError(AppError):
    status_code = 400


class UpstreamServiceError(AppError):
    """Wraps a failure from an external service call (e.g. OpenRouter)."""

    status_code = 502


class ContextBudgetError(AppError):
    """The prompt can't fit the target model's context window even before
    reserving room for its completion (and, for the compare paths, even
    after compacting the input) -- the caller should pick a
    larger-context model or send less. Surfaced instead of silently
    truncating the middle of an oversized prompt.
    """

    status_code = 413
