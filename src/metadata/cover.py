"""Cover art download and resize."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.metadata.utils import _http_get_bytes


def download_cover_image(
    url: str, timeout: float, max_size: int = 500
) -> tuple[bytes, str] | None:
    """Download and optionally resize cover art image."""
    result = _http_get_bytes(url, timeout)
    if not result:
        return None
    data, content_type = result
    if not data:
        return None
    mime = "image/jpeg"
    if "png" in content_type:
        mime = "image/png"
    try:
        from io import BytesIO

        from PIL import Image

        img = Image.open(BytesIO(data))
        if img.width > max_size or img.height > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
            buf = BytesIO()
            fmt = "JPEG" if "jpeg" in mime else "PNG"
            img.convert("RGB").save(buf, format=fmt)
            data = buf.getvalue()
            mime = "image/jpeg"
    except Exception:
        logger.debug("Cover resize failed, using original")
    return data, mime


def load_default_cover(path_str: str) -> tuple[bytes, str] | None:
    """Load default cover image from configured path."""
    path = Path(path_str)
    if not path.is_file():
        return None
    try:
        data = path.read_bytes()
    except OSError:
        return None
    mime = "image/jpeg"
    if path.suffix.lower() == ".png":
        mime = "image/png"
    return data, mime
