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
RESOLUTION_DEFAULT: str = "720p"
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

# Allowed domain suffixes for YouTube URLs (matches *.youtube.com, etc.)
YT_DOMAIN_SUFFIXES: frozenset[str] = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
        "youtubekids.com",
        "youtube.googleapis.com",
    }
)

# HTTP User-Agent (Microsoft Edge)
USER_AGENT: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    " AppleWebKit/537.36 (KHTML, like Gecko)"
    " Chrome/150.0.0.0 Safari/537.36 Edg/150.0.4078.83"
)

# Valid URI path patterns that indicate a YouTube video URL.
# Each pattern is matched against the path component of the URL.
YT_PATH_REGEX: re.Pattern[str] = re.compile(
    r"/(?:watch|v|embed|e|shorts|live|movie|clip)(?:/|$|\?)"
)

# Bun binary download
BUN_VERSION: str = "latest"
BUN_URL_TEMPLATE: str = (
    "https://github.com/oven-sh/bun/releases/download/"
    "bun-{version}/bun-{platform}-{arch}.zip"
)
