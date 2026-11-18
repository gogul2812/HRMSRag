"""Object storage abstraction — local filesystem (dev) or S3-compatible."""

from __future__ import annotations

import logging
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


class ObjectStorage:
    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        raise NotImplementedError

    def get(self, key: str) -> bytes:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError


class LocalObjectStorage(ObjectStorage):
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Prevent path traversal
        path = (self.root / key).resolve()
        if not str(path).startswith(str(self.root.resolve())):
            raise ValueError("Invalid storage key")
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        path = self._path(key)
        path.write_bytes(data)
        logger.info("Stored object locally key=%s bytes=%s", key, len(data))
        return key

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()


class S3ObjectStorage(ObjectStorage):
    def __init__(self) -> None:
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError(
                "boto3 required for S3 storage. pip install 'rag-platform-ingestion-service[s3]'"
            ) from exc
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint,
            aws_access_key_id=settings.s3_access_key,
            aws_secret_access_key=settings.s3_secret_key,
            region_name=settings.s3_region,
        )

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        extra = {}
        if content_type:
            extra["ContentType"] = content_type
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **extra)
        return key

    def get(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_object_storage() -> ObjectStorage:
    backend = (settings.storage_backend or "local").lower()
    if backend == "s3":
        return S3ObjectStorage()
    return LocalObjectStorage(settings.local_storage_path)
