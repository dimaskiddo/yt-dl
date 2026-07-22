"""Single source of truth for all constants, enums, and configuration values."""

from __future__ import annotations

import re
from enum import StrEnum
from pathlib import Path


class AudioFormat(StrEnum):
    """Supported audio output formats."""

    MP3 = "mp3"
    AAC = "aac"
    OPUS = "opus"


class VideoFormat(StrEnum):
    """Supported video output formats."""

    MP4 = "mp4"


# Bitrate options
BITRATE_DEFAULT: str = "192K"
BITRATE_OPTIONS: tuple[str, ...] = ("128K", "192K", "256K", "320K")

# Resolution options
RESOLUTION_DEFAULT: str = "1080p"
RESOLUTION_OPTIONS: tuple[str, ...] = ("360p", "480p", "720p", "1080p", "1440p")

# Format defaults
AUDIO_FORMAT_DEFAULT: AudioFormat = AudioFormat.MP3
VIDEO_FORMAT_DEFAULT: VideoFormat = VideoFormat.MP4

# Workspace paths
WORKSPACE_ROOT: Path = Path("workspace")
WORKSPACE_BIN: Path = WORKSPACE_ROOT / "bin"
WORKSPACE_AUDIOS: Path = WORKSPACE_ROOT / "audios"
WORKSPACE_VIDEOS: Path = WORKSPACE_ROOT / "videos"
WORKSPACE_TMP: Path = WORKSPACE_ROOT / "tmp"
WORKSPACE_LOGS: Path = WORKSPACE_ROOT / "logs"
GRADIO_TEMP_DIR: Path = WORKSPACE_TMP / "gradio"

# Video ID validation (YouTube 11-char alphanumeric + hyphens/underscores)
YT_ID_PATTERN: re.Pattern[str] = re.compile(r"^[A-Za-z0-9_-]{11}$")

# Server defaults
DEFAULT_HOST: str = "127.0.0.1"
DEFAULT_PORT: int = 7860

# URL validation
MAX_URL_LENGTH: int = 2048
YT_DOMAINS: frozenset[str] = frozenset({
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtu.be",
})

# Bun binary download
BUN_VERSION: str = "latest"
BUN_URL_TEMPLATE: str = (
    "https://github.com/oven-sh/bun/releases/download/"
    "bun-{version}/bun-{platform}-{arch}.zip"
)
