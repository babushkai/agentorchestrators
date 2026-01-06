"""S3-compatible object storage client."""

import io
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, AsyncGenerator

import structlog
from aiobotocore.session import get_session

from agent_orchestrator.config import S3Settings

logger = structlog.get_logger(__name__)


class ObjectStore:
    """S3-compatible object storage client for storing artifacts and checkpoints."""

    def __init__(self, settings: S3Settings) -> None:
        self._settings = settings
        self._session = get_session()

    @asynccontextmanager
    async def _get_client(self) -> AsyncGenerator[Any, None]:
        """Get an S3 client context."""
        async with self._session.create_client(
            "s3",
            endpoint_url=self._settings.endpoint_url,
            aws_access_key_id=self._settings.access_key_id,
            aws_secret_access_key=self._settings.secret_access_key.get_secret_value(),
            region_name=self._settings.region,
        ) as client:
            yield client

    async def ensure_bucket(self) -> None:
        """Ensure the bucket exists, create if not."""
        async with self._get_client() as client:
            try:
                await client.head_bucket(Bucket=self._settings.bucket)
            except Exception:
                await client.create_bucket(Bucket=self._settings.bucket)
                logger.info("Bucket created", bucket=self._settings.bucket)

    async def upload(
        self,
        key: str,
        data: bytes | str | io.BytesIO,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> str:
        """
        Upload an object to storage.

        Args:
            key: Object key (path)
            data: Object data
            content_type: MIME type
            metadata: Optional metadata

        Returns:
            Object URL
        """
        if isinstance(data, str):
            data = data.encode("utf-8")
        elif isinstance(data, io.BytesIO):
            data = data.read()

        async with self._get_client() as client:
            await client.put_object(
                Bucket=self._settings.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                Metadata=metadata or {},
            )

        logger.debug("Object uploaded", key=key, size=len(data))
        return f"{self._settings.endpoint_url}/{self._settings.bucket}/{key}"

    async def download(self, key: str) -> bytes:
        """
        Download an object from storage.

        Args:
            key: Object key (path)

        Returns:
            Object data as bytes
        """
        async with self._get_client() as client:
            response = await client.get_object(
                Bucket=self._settings.bucket,
                Key=key,
            )
            async with response["Body"] as stream:
                data = await stream.read()

        logger.debug("Object downloaded", key=key, size=len(data))
        return data

    async def download_stream(self, key: str) -> AsyncGenerator[bytes, None]:
        """
        Stream an object from storage.

        Args:
            key: Object key (path)

        Yields:
            Chunks of object data
        """
        async with self._get_client() as client:
            response = await client.get_object(
                Bucket=self._settings.bucket,
                Key=key,
            )
            async with response["Body"] as stream:
                async for chunk in stream.iter_chunks():
                    yield chunk

    async def delete(self, key: str) -> bool:
        """
        Delete an object from storage.

        Args:
            key: Object key (path)

        Returns:
            True if deleted, False if not found
        """
        async with self._get_client() as client:
            try:
                await client.delete_object(
                    Bucket=self._settings.bucket,
                    Key=key,
                )
                logger.debug("Object deleted", key=key)
                return True
            except Exception:
                return False

    async def exists(self, key: str) -> bool:
        """
        Check if an object exists.

        Args:
            key: Object key (path)

        Returns:
            True if exists, False otherwise
        """
        async with self._get_client() as client:
            try:
                await client.head_object(
                    Bucket=self._settings.bucket,
                    Key=key,
                )
                return True
            except Exception:
                return False

    async def list_objects(
        self,
        prefix: str = "",
        max_keys: int = 1000,
    ) -> list[dict[str, Any]]:
        """
        List objects with a prefix.

        Args:
            prefix: Key prefix to filter by
            max_keys: Maximum number of keys to return

        Returns:
            List of object metadata
        """
        async with self._get_client() as client:
            response = await client.list_objects_v2(
                Bucket=self._settings.bucket,
                Prefix=prefix,
                MaxKeys=max_keys,
            )

        objects = []
        for obj in response.get("Contents", []):
            objects.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"],
                "etag": obj.get("ETag", "").strip('"'),
            })

        return objects

    async def get_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """
        Generate a presigned URL for temporary access.

        Args:
            key: Object key (path)
            expires_in: URL expiration in seconds
            method: S3 method (get_object or put_object)

        Returns:
            Presigned URL
        """
        async with self._get_client() as client:
            url = await client.generate_presigned_url(
                method,
                Params={
                    "Bucket": self._settings.bucket,
                    "Key": key,
                },
                ExpiresIn=expires_in,
            )
        return url

    async def copy(self, source_key: str, dest_key: str) -> None:
        """
        Copy an object within the bucket.

        Args:
            source_key: Source object key
            dest_key: Destination object key
        """
        async with self._get_client() as client:
            await client.copy_object(
                Bucket=self._settings.bucket,
                CopySource={"Bucket": self._settings.bucket, "Key": source_key},
                Key=dest_key,
            )
        logger.debug("Object copied", source=source_key, dest=dest_key)


# Global store instance
_object_store: ObjectStore | None = None


async def get_object_store(settings: S3Settings) -> ObjectStore:
    """Get or create the object store."""
    global _object_store
    if _object_store is None:
        _object_store = ObjectStore(settings)
        await _object_store.ensure_bucket()
    return _object_store
