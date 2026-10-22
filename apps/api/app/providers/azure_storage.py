"""Managed-identity Blob storage with delivery through the authorized media route.

The browser never needs access to the storage endpoint. This also works when an
Azure Policy requires private endpoints and disables shared-key authentication.
"""

from collections.abc import Iterator
from email.utils import format_datetime
from functools import lru_cache
from typing import BinaryIO

from azure.core import MatchConditions
from azure.core.exceptions import AzureError, ResourceNotFoundError
from azure.identity import ManagedIdentityCredential
from azure.storage.blob import BlobServiceClient, ContentSettings
from fastapi.responses import Response, StreamingResponse

from app.core.exceptions import AppError

CHUNK_BYTES = 1024 * 1024


def byte_range(header: str | None, size: int) -> tuple[int, int] | None:
    """Parse one inclusive byte range; ignore unsupported units/multipart ranges."""
    if not header or not header.startswith("bytes=") or "," in header:
        return None
    if len(header) > 128:
        raise ValueError("Invalid range")
    start_text, separator, end_text = header[6:].partition("-")
    if not separator or (start_text and not start_text.isascii()) or (end_text and not end_text.isascii()):
        raise ValueError("Invalid range")
    if not start_text:
        if not end_text.isdigit() or int(end_text) == 0 or size == 0:
            raise ValueError("Invalid suffix range")
        return max(0, size - int(end_text)), size - 1
    if not start_text.isdigit() or (end_text and not end_text.isdigit()):
        raise ValueError("Invalid range")
    start = int(start_text)
    end = min(int(end_text), size - 1) if end_text else size - 1
    if start >= size or end < start:
        raise ValueError("Unsatisfiable range")
    return start, end


class AzureBlobStorage:
    def __init__(self, account_url: str, container: str, client_id: str) -> None:
        credential = ManagedIdentityCredential(client_id=client_id or None)
        self.client = BlobServiceClient(
            account_url=account_url,
            credential=credential,
            max_single_get_size=CHUNK_BYTES,
            max_chunk_get_size=CHUNK_BYTES,
            max_single_put_size=4 * CHUNK_BYTES,
            max_block_size=4 * CHUNK_BYTES,
            connection_timeout=10,
            read_timeout=30,
        )
        self.container = container

    def save(self, key: str, content: bytes, content_type: str) -> None:
        self._upload(key, content, content_type)

    def save_file(self, key: str, source: BinaryIO, content_type: str) -> None:
        source.seek(0)
        self._upload(key, source, content_type)

    def _upload(self, key: str, content: bytes | BinaryIO, content_type: str) -> None:
        try:
            self.client.get_blob_client(self.container, key).upload_blob(
                content, overwrite=True, max_concurrency=1,
                content_settings=ContentSettings(content_type=content_type),
            )
        except AzureError as exc:
            raise AppError(503, "STORAGE_UNAVAILABLE", "File storage is temporarily unavailable") from exc

    def delete(self, key: str) -> None:
        try:
            self.client.get_blob_client(self.container, key).delete_blob(delete_snapshots="include")
        except ResourceNotFoundError:
            pass
        except AzureError as exc:
            raise AppError(503, "STORAGE_UNAVAILABLE", "File storage is temporarily unavailable") from exc

    def signed_url(self, key: str) -> None:
        # Keep authorization, account revocation and publication checks in the API.
        # A SAS URL cannot bypass a storage account's private network restriction.
        return None

    def response(self, key: str, content_type: str, *, method: str,
                 range_header: str | None, if_range: str | None) -> Response:
        blob = self.client.get_blob_client(self.container, key)
        try:
            properties = blob.get_blob_properties()
            size = properties.size
            headers = {
                "Accept-Ranges": "bytes", "Content-Disposition": "inline",
                "X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store",
                "ETag": properties.etag,
                "Last-Modified": format_datetime(properties.last_modified, usegmt=True),
            }
            # Range only applies to GET. A stale If-Range validator requests the
            # complete current representation, never bytes from a changed object.
            requested_range = range_header if method == "GET" else None
            if if_range and if_range not in {headers["ETag"], headers["Last-Modified"]}:
                requested_range = None
            try:
                selected = byte_range(requested_range, size)
            except ValueError:
                return Response(status_code=416, headers={**headers, "Content-Range": f"bytes */{size}"})
            start, end = selected if selected else (0, size - 1)
            length = end - start + 1
            headers["Content-Length"] = str(length)
            if selected:
                headers["Content-Range"] = f"bytes {start}-{end}/{size}"
            status = 206 if selected else 200
            if method == "HEAD" or size == 0:
                return Response(status_code=status, media_type=content_type, headers=headers)
            download = blob.download_blob(
                offset=start, length=length, max_concurrency=1,
                etag=properties.etag, match_condition=MatchConditions.IfNotModified,
            )
        except ResourceNotFoundError as exc:
            raise AppError(404, "MEDIA_NOT_FOUND", "Media file not found") from exc
        except AzureError as exc:
            raise AppError(503, "STORAGE_UNAVAILABLE", "File storage is temporarily unavailable") from exc

        def chunks() -> Iterator[bytes]:
            # The SDK reads at most CHUNK_BYTES per chunk; never load a complete
            # exercise video into memory. Starlette iterates this in its thread pool.
            yield from download.chunks()

        return StreamingResponse(chunks(), status_code=status, media_type=content_type, headers=headers)


@lru_cache(maxsize=4)
def azure_storage(account_url: str, container: str, client_id: str) -> AzureBlobStorage:
    # Reuse token/HTTP pools across requests instead of contacting managed identity
    # once per file or download range. The SDK refreshes access tokens as needed.
    return AzureBlobStorage(account_url, container, client_id)
