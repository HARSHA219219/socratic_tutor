"""Disk storage for chat images. SQLite only keeps the generated key + metadata."""
import asyncio
import base64
import re
import uuid
from pathlib import Path
from typing import Optional, Tuple

from app.core.config import settings

_KEY_RE = re.compile(r"^[0-9a-f]{32}\.(jpg|png|webp)$")
_EXT = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}


def detect_image_type(data: bytes) -> Optional[str]:
    """Identify the format from magic bytes; the filename/Content-Type are never trusted."""
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _storage_dir() -> Path:
    path = Path(settings.IMAGE_STORAGE_DIR).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_image_path(key: str) -> Path:
    if not _KEY_RE.match(key or ""):
        raise ValueError("Invalid image key")
    base = _storage_dir()
    path = (base / key).resolve()
    if path.parent != base:
        raise ValueError("Invalid image key")
    return path


async def save_image(data: bytes, mime_type: str) -> str:
    key = f"{uuid.uuid4().hex}.{_EXT[mime_type]}"
    await asyncio.to_thread(resolve_image_path(key).write_bytes, data)
    return key


async def load_image_data_url(key: str, mime_type: str) -> Optional[str]:
    try:
        data = await asyncio.to_thread(resolve_image_path(key).read_bytes)
    except (OSError, ValueError):
        return None
    return f"data:{mime_type};base64,{base64.b64encode(data).decode()}"


def validate_upload(data: bytes) -> Tuple[Optional[str], Optional[str]]:
    """Returns (mime_type, error)."""
    if not data:
        return None, "The image is empty."
    if len(data) > settings.MAX_IMAGE_BYTES:
        return None, f"Image is too large (max {settings.MAX_IMAGE_BYTES // (1024 * 1024)} MB)."
    mime = detect_image_type(data)
    if not mime:
        return None, "Unsupported image type. Please upload a JPG, PNG or WebP image."
    return mime, None
