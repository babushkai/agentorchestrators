"""File operations tool for object storage."""

import mimetypes
import os
from typing import Any, Literal
from uuid import UUID

import structlog
from pydantic import BaseModel, Field

from agent_orchestrator.core.agents.definition import ToolConfig
from agent_orchestrator.core.agents.tools import Tool
from agent_orchestrator.infrastructure.storage.object_store import ObjectStore

logger = structlog.get_logger(__name__)


class FileToolConfig(BaseModel):
    """Configuration for the file operations tool."""

    max_file_size_bytes: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum file size in bytes for read/write operations.",
    )
    allowed_extensions: list[str] | None = Field(
        default=None,
        description="Allowed file extensions. None means all allowed.",
    )
    blocked_extensions: list[str] = Field(
        default_factory=lambda: [".exe", ".dll", ".so", ".sh", ".bat", ".cmd", ".ps1"],
        description="Blocked file extensions (security).",
    )


class FileOperationsTool(Tool):
    """Tool for file operations using object storage.

    Files are sandboxed to the task namespace: tasks/{task_id}/files/
    """

    def __init__(
        self,
        object_store: ObjectStore,
        task_id: UUID,
        config: FileToolConfig | None = None,
    ) -> None:
        tool_config = ToolConfig(
            tool_id="builtin_file_operations",
            name="file_operations",
            description=(
                "Read, write, list, and manage files in object storage. "
                "Files are stored in a task-specific namespace. "
                "Operations: read, write, list, delete, exists, info."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "enum": ["read", "write", "list", "delete", "exists", "info"],
                        "description": "File operation to perform",
                    },
                    "path": {
                        "type": "string",
                        "description": (
                            "File path relative to task namespace. "
                            "Example: 'output/result.json'"
                        ),
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write (for write operation)",
                    },
                    "content_type": {
                        "type": "string",
                        "description": "MIME type for write operation",
                        "default": "text/plain",
                    },
                    "encoding": {
                        "type": "string",
                        "description": "Text encoding for read operation",
                        "default": "utf-8",
                    },
                    "max_keys": {
                        "type": "integer",
                        "description": "Maximum files to list",
                        "default": 100,
                    },
                },
                "required": ["operation", "path"],
            },
            timeout_seconds=60.0,
        )
        super().__init__(tool_config)
        self._store = object_store
        self._task_id = task_id
        self._file_config = config or FileToolConfig()
        self._base_path = f"tasks/{task_id}/files"

    def _sanitize_path(self, path: str) -> str:
        """Sanitize and normalize the file path.

        Prevents directory traversal attacks.
        """
        # Remove leading/trailing slashes and normalize
        path = path.strip("/")

        # Prevent directory traversal
        normalized = os.path.normpath(path)
        if normalized.startswith("..") or normalized.startswith("/"):
            raise ValueError("Invalid path: directory traversal not allowed")

        # Check for blocked patterns
        if ".." in path:
            raise ValueError("Invalid path: '..' not allowed")

        return normalized

    def _get_full_path(self, path: str) -> str:
        """Get the full object storage path."""
        sanitized = self._sanitize_path(path)
        return f"{self._base_path}/{sanitized}"

    def _validate_extension(self, path: str) -> str | None:
        """Validate file extension against allowed/blocked lists."""
        _, ext = os.path.splitext(path)
        ext = ext.lower()

        if ext in self._file_config.blocked_extensions:
            return f"Extension '{ext}' is blocked for security reasons"

        if self._file_config.allowed_extensions is not None:
            if ext not in self._file_config.allowed_extensions:
                return f"Extension '{ext}' is not allowed"

        return None

    async def execute(
        self,
        operation: Literal["read", "write", "list", "delete", "exists", "info"],
        path: str,
        content: str | None = None,
        content_type: str = "text/plain",
        encoding: str = "utf-8",
        max_keys: int = 100,
    ) -> dict[str, Any]:
        """Execute a file operation."""
        try:
            match operation:
                case "read":
                    return await self._read_file(path, encoding)
                case "write":
                    if content is None:
                        return {"error": "Content required for write operation"}
                    return await self._write_file(path, content, content_type)
                case "list":
                    return await self._list_files(path, max_keys)
                case "delete":
                    return await self._delete_file(path)
                case "exists":
                    return await self._file_exists(path)
                case "info":
                    return await self._file_info(path)
                case _:
                    return {"error": f"Unknown operation: {operation}"}
        except ValueError as e:
            return {"error": str(e)}
        except Exception as e:
            logger.warning(
                "File operation failed",
                operation=operation,
                path=path,
                error=str(e),
            )
            return {"error": f"Operation failed: {e}"}

    async def _read_file(self, path: str, encoding: str) -> dict[str, Any]:
        """Read a file from storage."""
        full_path = self._get_full_path(path)

        # Check if file exists
        if not await self._store.exists(full_path):
            return {"error": f"File not found: {path}"}

        # Download file
        data = await self._store.download(full_path)

        # Check size
        if len(data) > self._file_config.max_file_size_bytes:
            return {
                "error": f"File too large: {len(data)} bytes exceeds limit",
                "size_bytes": len(data),
            }

        # Try to decode as text
        try:
            content = data.decode(encoding)
            return {
                "path": path,
                "content": content,
                "size_bytes": len(data),
                "encoding": encoding,
            }
        except UnicodeDecodeError:
            return {
                "path": path,
                "error": "Binary file cannot be read as text",
                "size_bytes": len(data),
                "is_binary": True,
            }

    async def _write_file(
        self,
        path: str,
        content: str,
        content_type: str,
    ) -> dict[str, Any]:
        """Write a file to storage."""
        # Validate extension
        ext_error = self._validate_extension(path)
        if ext_error:
            return {"error": ext_error}

        full_path = self._get_full_path(path)

        # Check content size
        data = content.encode("utf-8")
        if len(data) > self._file_config.max_file_size_bytes:
            return {"error": f"Content too large: {len(data)} bytes exceeds limit"}

        # Guess content type if not provided
        if content_type == "text/plain":
            guessed_type, _ = mimetypes.guess_type(path)
            if guessed_type:
                content_type = guessed_type

        # Upload file
        url = await self._store.upload(
            key=full_path,
            data=data,
            content_type=content_type,
            metadata={"task_id": str(self._task_id)},
        )

        logger.info(
            "File written",
            path=path,
            full_path=full_path,
            size_bytes=len(data),
        )

        return {
            "path": path,
            "size_bytes": len(data),
            "content_type": content_type,
            "url": url,
            "success": True,
        }

    async def _list_files(self, path: str, max_keys: int) -> dict[str, Any]:
        """List files in a directory."""
        # For list, path is a prefix
        prefix = self._get_full_path(path)
        if not prefix.endswith("/"):
            prefix += "/"

        # Handle empty path (list root)
        if path.strip() == "" or path.strip() == "/":
            prefix = f"{self._base_path}/"

        objects = await self._store.list_objects(prefix=prefix, max_keys=max_keys)

        # Convert to relative paths
        files = []
        for obj in objects:
            relative_path = obj["key"].replace(f"{self._base_path}/", "")
            files.append({
                "path": relative_path,
                "size_bytes": obj["size"],
                "last_modified": obj["last_modified"].isoformat() if obj.get("last_modified") else None,
            })

        return {
            "path": path,
            "files": files,
            "count": len(files),
        }

    async def _delete_file(self, path: str) -> dict[str, Any]:
        """Delete a file from storage."""
        full_path = self._get_full_path(path)

        # Check if file exists
        if not await self._store.exists(full_path):
            return {"error": f"File not found: {path}"}

        # Delete file
        success = await self._store.delete(full_path)

        logger.info("File deleted", path=path, full_path=full_path)

        return {
            "path": path,
            "deleted": success,
        }

    async def _file_exists(self, path: str) -> dict[str, Any]:
        """Check if a file exists."""
        full_path = self._get_full_path(path)
        exists = await self._store.exists(full_path)

        return {
            "path": path,
            "exists": exists,
        }

    async def _file_info(self, path: str) -> dict[str, Any]:
        """Get file information."""
        full_path = self._get_full_path(path)

        # Check if file exists
        if not await self._store.exists(full_path):
            return {"error": f"File not found: {path}"}

        # Get metadata via list (includes size and last modified)
        objects = await self._store.list_objects(prefix=full_path, max_keys=1)

        if not objects:
            return {"error": f"File not found: {path}"}

        obj = objects[0]

        # Guess content type
        content_type, _ = mimetypes.guess_type(path)

        return {
            "path": path,
            "size_bytes": obj["size"],
            "last_modified": obj["last_modified"].isoformat() if obj.get("last_modified") else None,
            "content_type": content_type or "application/octet-stream",
            "etag": obj.get("etag"),
        }
