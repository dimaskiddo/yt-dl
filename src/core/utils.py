"""Shared utility functions — URL parsing, formatting, validation, SSRF guard."""

from __future__ import annotations

import ipaddress
from urllib.parse import parse_qs, urlparse

from src.core.constants import (
    MAX_URL_LENGTH,
    YT_DOMAIN_SUFFIXES,
    YT_ID_PATTERN,
    YT_PATH_REGEX,
)
from src.core.exceptions import InvalidURLError


def validate_youtube_url(url: str) -> str:
    """Validate and sanitize a YouTube URL against SSRF and invalid input.

    Checks scheme, hostname against YouTube domain suffixes, and verifies
    the URL path/query contains recognizable YouTube video patterns.

    Args:
        url: Raw URL string from user input.

    Returns:
        Cleaned URL string (https:// prepended if scheme missing).

    Raises:
        InvalidURLError: If URL fails any validation check.
    """
    cleaned = url.strip()

    if not cleaned:
        raise InvalidURLError("URL is empty")

    if len(cleaned) > MAX_URL_LENGTH:
        raise InvalidURLError(f"URL exceeds maximum length ({MAX_URL_LENGTH} chars)")

    # Naked video ID (11-char alphanumeric) — pass through directly
    if YT_ID_PATTERN.match(cleaned):
        return cleaned

    # Prepend https:// if scheme missing (urlparse needs it for hostname)
    if "://" not in cleaned:
        cleaned = "https://" + cleaned

    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower()

    if scheme not in ("http", "https"):
        raise InvalidURLError(f"URL scheme '{scheme}' is not allowed")

    # Upgrade http:// to https://
    if scheme == "http":
        cleaned = cleaned.replace("http://", "https://", 1)
        scheme = "https"

    if not hostname:
        raise InvalidURLError("URL has no hostname")

    # Normalize: strip www. prefix from hostname
    if hostname.startswith("www."):
        hostname = hostname[4:]
        cleaned = cleaned.replace("://www.", "://", 1)

    # Reject raw IP addresses
    try:
        ipaddress.ip_address(hostname)
        raise InvalidURLError("IP address URLs are not allowed")
    except ValueError:
        pass  # Not an IP — good, continue

    # Check hostname against YouTube domain suffixes (matches subdomains)
    if not _is_youtube_domain(hostname):
        raise InvalidURLError(f"Domain '{hostname}' is not a recognized YouTube domain")

    # Check that URL path/query contains recognizable YouTube video patterns
    if not _has_youtube_path(parsed):
        raise InvalidURLError(
            f"URL path does not match a known YouTube video format: {parsed.path or '/'}"
        )

    return cleaned


def extract_video_id(url: str) -> str:
    """Extract the 11-character YouTube video ID from various URL formats.

    Args:
        url: YouTube URL or video ID string.

    Returns:
        The 11-character video ID.

    Raises:
        InvalidURLError: If no valid video ID can be extracted.
    """
    url = url.strip()

    if YT_ID_PATTERN.match(url):
        return url

    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise InvalidURLError(f"Invalid URL: {url}") from e

    result = _extract_from_url(parsed)
    if result:
        return result

    raise InvalidURLError(f"Could not extract video ID from: {url}")


def _extract_from_url(parsed: object) -> str | None:
    """Extract video ID from a parsed URL.

    Args:
        parsed: Parsed URL object from urlparse().

    Returns:
        Video ID if found, None otherwise.
    """
    hostname = (getattr(parsed, "hostname", None) or "").lower()

    if "youtu.be" in hostname:
        path = getattr(parsed, "path", "")
        video_id = path.lstrip("/").split("/")[0].split("?")[0]
        if _valid_id(video_id):
            return video_id

    if "youtube.com" in hostname or "www.youtube.com" in hostname:
        path_parts = getattr(parsed, "path", "").strip("/").split("/")

        if "watch" in path_parts:
            query = parse_qs(getattr(parsed, "query", ""))
            ids = query.get("v", [])
            if ids and _valid_id(ids[0]):
                return ids[0]

        if len(path_parts) >= 2:
            video_id = path_parts[-1].split("?")[0]
            if _valid_id(video_id):
                return video_id

    return None


def _valid_id(video_id: str) -> bool:
    """Check if a string is a valid YouTube video ID."""
    return bool(YT_ID_PATTERN.match(video_id))


def _is_youtube_domain(hostname: str) -> bool:
    """Check if hostname is a YouTube domain or subdomain.

    Args:
        hostname: Lowercase hostname from URL.

    Returns:
        True if hostname matches a known YouTube domain suffix.
    """
    hostname = hostname.lower()
    return any(
        hostname == suffix or hostname.endswith("." + suffix)
        for suffix in YT_DOMAIN_SUFFIXES
    )


def _has_youtube_path(parsed: object) -> bool:
    """Check if URL path or query contains a recognizable YouTube video pattern.

    Args:
        parsed: Parsed URL object from urlparse().

    Returns:
        True if path or query matches known YouTube video URL patterns.
    """
    path = getattr(parsed, "path", "") or ""
    query = getattr(parsed, "query", "") or ""
    hostname = (getattr(parsed, "hostname", None) or "").lower()

    # youtu.be has no path prefix — the path IS the video ID
    if "youtu.be" in hostname:
        return True

    # Recognizable path patterns: /watch, /v/, /embed/, /e/, /shorts/, /live/
    if YT_PATH_REGEX.search(path):
        return True

    # Has v= query parameter (YouTube-style)
    return "v=" in query


def parse_resolution_height(resolution: str) -> int:
    """Extract numeric height from resolution string.

    Args:
        resolution: Resolution string like "1080p", "720p".

    Returns:
        Height in pixels (e.g., 1080).

    Raises:
        ValueError: If resolution string is invalid.
    """
    resolution = resolution.strip().lower()
    digits = "".join(c for c in resolution if c.isdigit())
    if not digits:
        raise ValueError(f"Invalid resolution format: '{resolution}'")
    return int(digits)


def format_bytes(size_bytes: int) -> str:
    """Format byte count as human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Human-readable string (e.g., "1.5 GB", "256.0 MB").
    """
    if size_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(size_bytes)
    unit_index = 0

    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"

    return f"{size:.1f} {units[unit_index]}"


def sanitize_filename(title: str) -> str:
    """Sanitize a video title for safe use as a filename component.

    Strips non-alphanumeric characters (except - and _), collapses
    whitespace to _, truncates to 50 chars.

    Args:
        title: Raw video title.

    Returns:
        Sanitized filename-safe string.
    """
    import re

    safe = re.sub(r"[^\w\s-]", "", title)
    safe = re.sub(r"\s+", "_", safe.strip())
    safe = safe.strip("_")
    return safe[:50] if safe else "untitled"
