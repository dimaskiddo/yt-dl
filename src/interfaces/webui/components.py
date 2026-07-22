"""Shared UI component constants and choice lists."""

from __future__ import annotations

from src.core.constants import (
    BITRATE_OPTIONS,
    RESOLUTION_OPTIONS,
    AudioFormat,
)

# Radio choices: (display label, value)
MODE_CHOICES: list[tuple[str, str]] = [("Audio", "audio"), ("Video", "video")]

# Dropdown choices
AUDIO_FORMAT_CHOICES: list[tuple[str, str]] = [
    (f.value.upper(), f.value) for f in AudioFormat
]
AUDIO_BITRATE_CHOICES: list[tuple[str, str]] = [(b, b) for b in BITRATE_OPTIONS]
VIDEO_RESOLUTION_CHOICES: list[tuple[str, str]] = [(r, r) for r in RESOLUTION_OPTIONS]
