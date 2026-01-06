"""Global error handling middleware."""

import traceback
from typing import Any

import structlog
from fastapi import Request, Response
from fastapi.responses import ORJSONResponse
from starlette.middleware.base import RequestResponseEndpoint

logger = structlog.get_logger(__name__)


class APIError(Exception):
    """Base exception for API errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details or {}


class NotFoundError(APIError):
    """Resource not found error."""

    def __init__(self, resource: str, resource_id: str) -> None:
        super().__init__(
            message=f"{resource} with id '{resource_id}' not found",
            status_code=404,
            error_code="NOT_FOUND",
            details={"resource": resource, "id": resource_id},
        )


class ValidationError(APIError):
    """Validation error."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            status_code=422,
            error_code="VALIDATION_ERROR",
            details=details or {},
        )


class ConflictError(APIError):
    """Resource conflict error."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message=message,
            status_code=409,
            error_code="CONFLICT",
        )


class RateLimitError(APIError):
    """Rate limit exceeded error."""

    def __init__(self, retry_after: int = 60) -> None:
        super().__init__(
            message="Rate limit exceeded",
            status_code=429,
            error_code="RATE_LIMIT_EXCEEDED",
            details={"retry_after": retry_after},
        )


async def error_handler_middleware(
    request: Request,
    call_next: RequestResponseEndpoint,
) -> Response:
    """Handle errors globally and return consistent error responses."""
    try:
        return await call_next(request)
    except APIError as e:
        logger.warning(
            "API error occurred",
            error_code=e.error_code,
            message=e.message,
            status_code=e.status_code,
            path=request.url.path,
        )
        return ORJSONResponse(
            status_code=e.status_code,
            content={
                "error": {
                    "code": e.error_code,
                    "message": e.message,
                    "details": e.details,
                }
            },
        )
    except Exception as e:
        logger.exception(
            "Unexpected error occurred",
            error=str(e),
            path=request.url.path,
            traceback=traceback.format_exc(),
        )
        return ORJSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_ERROR",
                    "message": "An unexpected error occurred",
                    "details": {},
                }
            },
        )
