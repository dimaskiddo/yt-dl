"""Shared HTTP helpers for metadata providers."""

from __future__ import annotations

import json
import urllib.request

from loguru import logger

from src.core.constants import USER_AGENT


def _http_get_json(
    url: str, timeout: float, headers: dict[str, str] | None = None
) -> dict | None:
    """GET a JSON API endpoint. Returns parsed dict or None on failure.

    Args:
        url: Request URL.
        timeout: HTTP timeout in seconds.
        headers: Optional extra headers (merged with User-Agent).

    Returns:
        Parsed JSON dict, or None on any error.
    """
    req_headers: dict[str, str] = {"User-Agent": USER_AGENT}
    if headers:
        req_headers.update(headers)

    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception:
        logger.debug("HTTP GET failed for {}", url)
        return None


def _http_get_bytes(url: str, timeout: float) -> tuple[bytes, str] | None:
    """GET raw bytes from URL. Returns (data, content_type) or None on failure.

    Args:
        url: Request URL.
        timeout: HTTP timeout in seconds.

    Returns:
        Tuple of (bytes, mime string), or None on any error.
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "")
    except Exception:
        logger.debug("HTTP GET failed for {}", url)
        return None
