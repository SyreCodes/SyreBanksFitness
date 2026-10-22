import os
import shutil
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import BinaryIO, Protocol

import boto3

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.providers.azure_storage import azure_storage


class StorageProvider(Protocol):
    def save(self, key: str, content: bytes, content_type: str) -> None: ...
    def save_file(self, key: str, source: BinaryIO, content_type: str) -> None: ...
    def delete(self, key: str) -> None: ...
    def signed_url(self, key: str) -> str | None: ...


class LocalStorage:
    def save(self, key: str, content: bytes, content_type: str) -> None:
        root = get_settings().media_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = root / key
        if path.parent != root:
            raise AppError(422, "INVALID_STORAGE_KEY", "Invalid storage key")
        path.write_bytes(content)
        path.chmod(0o600)

    def save_file(self, key: str, source: BinaryIO, content_type: str) -> None:
        root = get_settings().media_root.resolve()
        root.mkdir(parents=True, exist_ok=True)
        path = root / key
        if path.parent != root:
            raise AppError(422, "INVALID_STORAGE_KEY", "Invalid storage key")
        temporary: Path | None = None
        try:
            with NamedTemporaryFile(mode="wb", prefix=".upload-", dir=root, delete=False) as target:
                temporary = Path(target.name)
                source.seek(0)
                shutil.copyfileobj(source, target, length=1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            temporary.chmod(0o600)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    def signed_url(self, key: str) -> None:
        return None

    def delete(self, key: str) -> None:
        root = get_settings().media_root.resolve()
        path = (root / key).resolve()
        if path.parent != root:
            raise AppError(422, "INVALID_STORAGE_KEY", "Invalid storage key")
        path.unlink(missing_ok=True)

    def path(self, key: str) -> Path:
        root = get_settings().media_root.resolve()
        path = (root / key).resolve()
        if path.parent != root or not path.is_file():
            raise AppError(404, "MEDIA_NOT_FOUND", "Media file not found")
        return path


class S3Storage:
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.s3_bucket or not settings.s3_access_key or not settings.s3_secret_key:
            raise AppError(503, "STORAGE_UNAVAILABLE", "S3 storage is not configured")
        self.bucket = settings.s3_bucket
        self.client = boto3.client("s3", endpoint_url=settings.s3_endpoint_url or None, region_name=settings.s3_region, aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key)

    def save(self, key: str, content: bytes, content_type: str) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type)

    def save_file(self, key: str, source: BinaryIO, content_type: str) -> None:
        source.seek(0)
        self.client.upload_fileobj(source, self.bucket, key, ExtraArgs={"ContentType": content_type})

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def signed_url(self, key: str) -> str:
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=300)


def storage_provider() -> StorageProvider:
    settings = get_settings()
    if settings.storage_provider == "azure":
        return azure_storage(settings.azure_storage_account_url, settings.azure_storage_container,
                             settings.azure_managed_identity_client_id)
    return S3Storage() if settings.storage_provider == "s3" else LocalStorage()
