"""File upload and management API routes."""

import hashlib
import io
from datetime import datetime, timezone
from typing import Annotated, Any
from uuid import UUID, uuid4

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent_orchestrator.api.dependencies import (
    ObjectStoreDep,
    RedisDep,
)

logger = structlog.get_logger(__name__)
router = APIRouter()

# Constants
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_CONTENT_TYPES = {
    # Documents
    "application/pdf",
    "application/msword",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/plain",
    "text/csv",
    "text/markdown",
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    # Data
    "application/json",
    "application/xml",
    "text/xml",
}


class FileUploadResponse(BaseModel):
    """Response for file upload."""

    file_id: UUID
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    checksum: str
    created_at: datetime


class FileMetadata(BaseModel):
    """File metadata."""

    file_id: UUID
    task_id: UUID | None = None
    session_id: UUID | None = None
    filename: str
    original_filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    checksum: str
    parse_status: str = "pending"
    parsed_content: str | None = None
    created_at: datetime


class FileListResponse(BaseModel):
    """Response for listing files."""

    files: list[FileMetadata]
    count: int


@router.post("/tasks/{task_id}/files", response_model=FileUploadResponse)
async def upload_file_for_task(
    task_id: UUID,
    file: UploadFile,
    object_store: ObjectStoreDep,
    redis: RedisDep,
) -> FileUploadResponse:
    """Upload a file and attach it to a task.

    Args:
        task_id: Task ID to attach the file to.
        file: File to upload.
        object_store: Object storage client.
        redis: Redis client.

    Returns:
        File upload response with metadata.
    """
    return await _upload_file(
        file=file,
        object_store=object_store,
        redis=redis,
        task_id=task_id,
        session_id=None,
    )


@router.post("/sessions/{session_id}/files", response_model=FileUploadResponse)
async def upload_file_for_session(
    session_id: UUID,
    file: UploadFile,
    object_store: ObjectStoreDep,
    redis: RedisDep,
) -> FileUploadResponse:
    """Upload a file and attach it to a conversation session.

    Args:
        session_id: Session ID to attach the file to.
        file: File to upload.
        object_store: Object storage client.
        redis: Redis client.

    Returns:
        File upload response with metadata.
    """
    return await _upload_file(
        file=file,
        object_store=object_store,
        redis=redis,
        task_id=None,
        session_id=session_id,
    )


async def _upload_file(
    file: UploadFile,
    object_store: ObjectStoreDep,
    redis: RedisDep,
    task_id: UUID | None = None,
    session_id: UUID | None = None,
) -> FileUploadResponse:
    """Internal file upload handler."""
    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=f"Content type '{content_type}' not allowed. "
            f"Allowed types: {', '.join(sorted(ALLOWED_CONTENT_TYPES))}",
        )

    # Read file content
    content = await file.read()

    # Validate size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {MAX_FILE_SIZE // (1024 * 1024)}MB",
        )

    # Generate IDs and paths
    file_id = uuid4()
    original_filename = file.filename or "unnamed"
    # Sanitize filename
    safe_filename = "".join(
        c if c.isalnum() or c in ".-_" else "_" for c in original_filename
    )

    # Determine storage path based on context
    if task_id:
        storage_path = f"tasks/{task_id}/files/{file_id}/{safe_filename}"
    elif session_id:
        storage_path = f"sessions/{session_id}/files/{file_id}/{safe_filename}"
    else:
        storage_path = f"files/{file_id}/{safe_filename}"

    # Calculate checksum
    checksum = hashlib.sha256(content).hexdigest()

    # Upload to object storage
    try:
        await object_store.upload(
            key=storage_path,
            data=content,
            content_type=content_type,
            metadata={
                "file_id": str(file_id),
                "task_id": str(task_id) if task_id else "",
                "session_id": str(session_id) if session_id else "",
                "original_filename": original_filename,
                "checksum": checksum,
            },
        )
    except Exception as e:
        logger.error("Failed to upload file", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to upload file")

    # Store metadata in Redis
    now = datetime.now(timezone.utc)
    file_metadata = {
        "file_id": str(file_id),
        "task_id": str(task_id) if task_id else None,
        "session_id": str(session_id) if session_id else None,
        "filename": safe_filename,
        "original_filename": original_filename,
        "content_type": content_type,
        "size_bytes": len(content),
        "storage_path": storage_path,
        "checksum": checksum,
        "parse_status": "pending",
        "parsed_content": None,
        "created_at": now.isoformat(),
    }

    await redis.set(f"file:{file_id}", file_metadata, ttl=86400 * 30)  # 30 days

    # Add to task/session file list
    if task_id:
        await redis.client.sadd(f"task:{task_id}:files", str(file_id))
    if session_id:
        await redis.client.sadd(f"session:{session_id}:files", str(file_id))

    logger.info(
        "File uploaded",
        file_id=str(file_id),
        task_id=str(task_id) if task_id else None,
        session_id=str(session_id) if session_id else None,
        filename=safe_filename,
        size_bytes=len(content),
    )

    return FileUploadResponse(
        file_id=file_id,
        filename=safe_filename,
        original_filename=original_filename,
        content_type=content_type,
        size_bytes=len(content),
        storage_path=storage_path,
        checksum=checksum,
        created_at=now,
    )


@router.get("/tasks/{task_id}/files", response_model=FileListResponse)
async def list_task_files(
    task_id: UUID,
    redis: RedisDep,
) -> FileListResponse:
    """List all files attached to a task."""
    file_ids = await redis.client.smembers(f"task:{task_id}:files")

    files = []
    for fid in file_ids:
        metadata = await redis.get(f"file:{fid}")
        if metadata:
            metadata["file_id"] = UUID(metadata["file_id"])
            metadata["task_id"] = UUID(metadata["task_id"]) if metadata.get("task_id") else None
            metadata["session_id"] = UUID(metadata["session_id"]) if metadata.get("session_id") else None
            metadata["created_at"] = datetime.fromisoformat(metadata["created_at"])
            files.append(FileMetadata(**metadata))

    return FileListResponse(files=files, count=len(files))


@router.get("/sessions/{session_id}/files", response_model=FileListResponse)
async def list_session_files(
    session_id: UUID,
    redis: RedisDep,
) -> FileListResponse:
    """List all files attached to a conversation session."""
    file_ids = await redis.client.smembers(f"session:{session_id}:files")

    files = []
    for fid in file_ids:
        metadata = await redis.get(f"file:{fid}")
        if metadata:
            metadata["file_id"] = UUID(metadata["file_id"])
            metadata["task_id"] = UUID(metadata["task_id"]) if metadata.get("task_id") else None
            metadata["session_id"] = UUID(metadata["session_id"]) if metadata.get("session_id") else None
            metadata["created_at"] = datetime.fromisoformat(metadata["created_at"])
            files.append(FileMetadata(**metadata))

    return FileListResponse(files=files, count=len(files))


@router.get("/files/{file_id}")
async def get_file_metadata(
    file_id: UUID,
    redis: RedisDep,
) -> FileMetadata:
    """Get file metadata by ID."""
    metadata = await redis.get(f"file:{file_id}")
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")

    metadata["file_id"] = UUID(metadata["file_id"])
    metadata["task_id"] = UUID(metadata["task_id"]) if metadata.get("task_id") else None
    metadata["session_id"] = UUID(metadata["session_id"]) if metadata.get("session_id") else None
    metadata["created_at"] = datetime.fromisoformat(metadata["created_at"])

    return FileMetadata(**metadata)


@router.get("/files/{file_id}/download")
async def download_file(
    file_id: UUID,
    object_store: ObjectStoreDep,
    redis: RedisDep,
) -> StreamingResponse:
    """Download a file by ID."""
    metadata = await redis.get(f"file:{file_id}")
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")

    try:
        content = await object_store.download(metadata["storage_path"])
    except Exception as e:
        logger.error("Failed to download file", file_id=str(file_id), error=str(e))
        raise HTTPException(status_code=500, detail="Failed to download file")

    return StreamingResponse(
        io.BytesIO(content),
        media_type=metadata["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{metadata["original_filename"]}"',
            "Content-Length": str(metadata["size_bytes"]),
        },
    )


@router.delete("/files/{file_id}")
async def delete_file(
    file_id: UUID,
    object_store: ObjectStoreDep,
    redis: RedisDep,
) -> dict[str, Any]:
    """Delete a file by ID."""
    metadata = await redis.get(f"file:{file_id}")
    if not metadata:
        raise HTTPException(status_code=404, detail="File not found")

    # Delete from object storage
    try:
        await object_store.delete(metadata["storage_path"])
    except Exception as e:
        logger.warning("Failed to delete from object storage", error=str(e))

    # Remove from Redis
    await redis.delete(f"file:{file_id}")

    # Remove from task/session file lists
    if metadata.get("task_id"):
        await redis.client.srem(f"task:{metadata['task_id']}:files", str(file_id))
    if metadata.get("session_id"):
        await redis.client.srem(f"session:{metadata['session_id']}:files", str(file_id))

    logger.info("File deleted", file_id=str(file_id))

    return {"deleted": True, "file_id": str(file_id)}
