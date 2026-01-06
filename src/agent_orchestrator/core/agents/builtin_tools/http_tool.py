"""HTTP request tool for making API calls."""

import base64
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
import structlog
from pydantic import BaseModel, Field, SecretStr

from agent_orchestrator.core.agents.definition import ToolConfig
from agent_orchestrator.core.agents.tools import Tool

logger = structlog.get_logger(__name__)


class HTTPToolConfig(BaseModel):
    """Configuration for the HTTP tool."""

    allowed_domains: list[str] | None = Field(
        default=None,
        description="List of allowed domains. None means all domains allowed.",
    )
    blocked_domains: list[str] = Field(
        default_factory=lambda: ["localhost", "127.0.0.1", "0.0.0.0", "169.254.169.254"],
        description="List of blocked domains (security).",
    )
    max_response_size_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum response size in bytes.",
    )
    default_timeout: float = Field(
        default=30.0,
        description="Default request timeout in seconds.",
    )
    follow_redirects: bool = Field(
        default=True,
        description="Whether to follow redirects.",
    )
    max_redirects: int = Field(
        default=10,
        description="Maximum number of redirects to follow.",
    )


class HTTPTool(Tool):
    """Tool for making HTTP requests with authentication support."""

    def __init__(self, config: HTTPToolConfig | None = None) -> None:
        tool_config = ToolConfig(
            tool_id="builtin_http",
            name="http_request",
            description=(
                "Make HTTP requests to external APIs and web services. "
                "Supports GET, POST, PUT, PATCH, DELETE methods. "
                "Can include headers, query parameters, and request body. "
                "Supports authentication: none, basic, bearer, api_key."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
                        "description": "HTTP method",
                    },
                    "url": {
                        "type": "string",
                        "description": "Full URL to request",
                    },
                    "headers": {
                        "type": "object",
                        "description": "Request headers as key-value pairs",
                        "additionalProperties": {"type": "string"},
                    },
                    "params": {
                        "type": "object",
                        "description": "Query parameters as key-value pairs",
                        "additionalProperties": {"type": "string"},
                    },
                    "body": {
                        "description": "Request body (string or JSON object)",
                    },
                    "auth_type": {
                        "type": "string",
                        "enum": ["none", "basic", "bearer", "api_key"],
                        "description": "Authentication type",
                        "default": "none",
                    },
                    "auth_value": {
                        "type": "string",
                        "description": (
                            "Auth credential: token for bearer, api_key value, "
                            "or 'username:password' for basic auth"
                        ),
                    },
                    "api_key_header": {
                        "type": "string",
                        "description": "Header name for API key auth (default: X-API-Key)",
                        "default": "X-API-Key",
                    },
                    "timeout": {
                        "type": "number",
                        "description": "Request timeout in seconds",
                    },
                },
                "required": ["method", "url"],
            },
            timeout_seconds=60.0,
        )
        super().__init__(tool_config)
        self._http_config = config or HTTPToolConfig()

    async def execute(
        self,
        method: Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"],
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, str] | None = None,
        body: str | dict[str, Any] | None = None,
        auth_type: Literal["none", "basic", "bearer", "api_key"] = "none",
        auth_value: str | None = None,
        api_key_header: str = "X-API-Key",
        timeout: float | None = None,
    ) -> dict[str, Any]:
        """Execute an HTTP request."""
        # Validate URL domain
        validation_error = self._validate_url(url)
        if validation_error:
            return {"error": validation_error}

        # Build headers
        request_headers = headers.copy() if headers else {}

        # Add authentication
        if auth_type != "none" and auth_value:
            auth_header = self._build_auth_header(auth_type, auth_value, api_key_header)
            if auth_header:
                request_headers.update(auth_header)

        # Build request
        request_timeout = timeout or self._http_config.default_timeout

        try:
            async with httpx.AsyncClient(
                follow_redirects=self._http_config.follow_redirects,
                max_redirects=self._http_config.max_redirects,
            ) as client:
                # Prepare body
                json_body = None
                content = None
                if body is not None:
                    if isinstance(body, dict):
                        json_body = body
                        if "Content-Type" not in request_headers:
                            request_headers["Content-Type"] = "application/json"
                    else:
                        content = body

                response = await client.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    params=params,
                    json=json_body,
                    content=content,
                    timeout=request_timeout,
                )

                # Check response size
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > self._http_config.max_response_size_bytes:
                    return {
                        "error": f"Response too large: {content_length} bytes",
                        "status_code": response.status_code,
                    }

                # Read response with size limit
                response_body = await self._read_response(response)

                logger.info(
                    "HTTP request completed",
                    method=method,
                    url=url,
                    status_code=response.status_code,
                    response_size=len(response_body) if response_body else 0,
                )

                return {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                    "url": str(response.url),
                    "is_success": response.is_success,
                }

        except httpx.TimeoutException:
            logger.warning("HTTP request timeout", method=method, url=url)
            return {"error": f"Request timed out after {request_timeout}s"}
        except httpx.RequestError as e:
            logger.warning("HTTP request error", method=method, url=url, error=str(e))
            return {"error": f"Request failed: {e}"}
        except Exception as e:
            logger.error("HTTP request unexpected error", method=method, url=url, error=str(e))
            return {"error": f"Unexpected error: {e}"}

    def _validate_url(self, url: str) -> str | None:
        """Validate URL against allowed/blocked domains."""
        try:
            parsed = urlparse(url)
            domain = parsed.hostname or ""

            # Check blocked domains
            for blocked in self._http_config.blocked_domains:
                if domain == blocked or domain.endswith(f".{blocked}"):
                    return f"Domain '{domain}' is blocked for security reasons"

            # Check allowed domains (if configured)
            if self._http_config.allowed_domains is not None:
                allowed = False
                for allow in self._http_config.allowed_domains:
                    if domain == allow or domain.endswith(f".{allow}"):
                        allowed = True
                        break
                if not allowed:
                    return f"Domain '{domain}' is not in the allowed list"

            return None
        except Exception as e:
            return f"Invalid URL: {e}"

    def _build_auth_header(
        self,
        auth_type: str,
        auth_value: str,
        api_key_header: str,
    ) -> dict[str, str]:
        """Build authentication header."""
        match auth_type:
            case "bearer":
                return {"Authorization": f"Bearer {auth_value}"}
            case "basic":
                # Expect 'username:password' format
                encoded = base64.b64encode(auth_value.encode()).decode()
                return {"Authorization": f"Basic {encoded}"}
            case "api_key":
                return {api_key_header: auth_value}
            case _:
                return {}

    async def _read_response(self, response: httpx.Response) -> str | dict[str, Any] | None:
        """Read and parse response body with size limit."""
        content_type = response.headers.get("content-type", "")

        # Read raw bytes
        raw_bytes = await response.aread()

        # Check size
        if len(raw_bytes) > self._http_config.max_response_size_bytes:
            return f"[Response truncated: {len(raw_bytes)} bytes exceeds limit]"

        # Try to parse as JSON
        if "application/json" in content_type:
            try:
                return response.json()
            except Exception:
                pass

        # Return as text
        try:
            return raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            return f"[Binary response: {len(raw_bytes)} bytes]"
