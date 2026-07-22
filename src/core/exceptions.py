"""Custom exception hierarchy for YT-DL."""

from __future__ import annotations


class YTDownloaderError(Exception):
    """Base exception for all YT-DL errors."""


class ConfigValidationError(YTDownloaderError):
    """Raised when config.yaml is invalid or missing required fields."""


class DownloadError(YTDownloaderError):
    """Raised when video downloading or processing fails."""


class FFmpegError(YTDownloaderError):
    """Raised when FFmpeg encoding or merging fails."""


class InvalidURLError(YTDownloaderError):
    """Raised when a YouTube URL cannot be parsed or is invalid."""
