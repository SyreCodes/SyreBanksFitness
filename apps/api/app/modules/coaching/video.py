"""Validation and public upload policy for exercise demonstrations."""

from dataclasses import dataclass
from hashlib import sha256

from fastapi import UploadFile

from app.core.config import get_settings
from app.core.exceptions import AppError

VIDEO_TYPES = ("video/mp4", "video/webm", "video/quicktime")
CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class ValidatedVideo:
    size: int
    content_type: str
    extension: str
    sha256: str


def upload_policy() -> dict:
    return {"max_bytes": get_settings().video_max_upload_bytes, "accepted_types": list(VIDEO_TYPES)}


def _extension(content_type: str, header: bytes) -> str | None:
    if content_type == "video/mp4" and len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] != b"qt  ":
        return "mp4"
    if content_type == "video/quicktime" and len(header) >= 12 and header[4:8] == b"ftyp" and header[8:12] == b"qt  ":
        return "mov"
    if content_type == "video/webm" and header.startswith(b"\x1a\x45\xdf\xa3") and b"webm" in header[:4096]:
        return "webm"
    return None


async def validate_video(file: UploadFile) -> ValidatedVideo:
    filename = (file.filename or "").strip()
    if not filename or len(filename) > 255 or filename in {".", ".."}:
        raise AppError(422, "INVALID_FILENAME", "Choose a video file with a valid name")
    if file.content_type not in VIDEO_TYPES:
        raise AppError(422, "UNSUPPORTED_VIDEO_TYPE", "Upload an MP4, WebM, or MOV demonstration video",
                       {"accepted_types": list(VIDEO_TYPES)})

    limit = get_settings().video_max_upload_bytes
    if file.size is not None and file.size > limit:
        raise AppError(413, "UPLOAD_TOO_LARGE", f"Video exceeds the {get_settings().video_max_upload_mb} MB upload limit.",
                       {"max_bytes": limit})
    size = 0
    digest = sha256()
    header = bytearray()
    try:
        while chunk := await file.read(CHUNK_SIZE):
            size += len(chunk)
            if size > limit:
                raise AppError(413, "UPLOAD_TOO_LARGE", f"Video exceeds the {get_settings().video_max_upload_mb} MB upload limit.",
                               {"max_bytes": limit})
            digest.update(chunk)
            if len(header) < 4096:
                header.extend(chunk[:4096 - len(header)])
    finally:
        await file.seek(0)

    if size == 0:
        raise AppError(422, "EMPTY_UPLOAD", "Choose a nonempty video file")
    extension = _extension(file.content_type, bytes(header))
    if extension is None:
        raise AppError(422, "UNSUPPORTED_VIDEO_TYPE", "The file content does not match its video format",
                       {"accepted_types": list(VIDEO_TYPES)})
    return ValidatedVideo(size=size, content_type=file.content_type, extension=extension, sha256=digest.hexdigest())
