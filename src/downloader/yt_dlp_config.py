"""yt-dlp options builder with platform-specific configuration."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.core.constants import USER_AGENT
from src.core.workspace import get_ffmpeg_path


class YTDLLogger:
    """Suppress yt-dlp debug/info output, pass warnings/errors to loguru."""

    def debug(self, msg: str) -> None:
        """Suppress debug messages."""

    def info(self, msg: str) -> None:
        """Suppress info messages."""

    def warning(self, msg: str) -> None:
        """Log yt-dlp warnings via loguru."""
        logger.warning("yt-dlp: {}", msg)

    def error(self, msg: str) -> None:
        """Log yt-dlp errors via loguru."""
        logger.error("yt-dlp: {}", msg)


def build_audio_format_string() -> str:
    """Build yt-dlp format selection for audio-only download.

    Returns:
        Format string prioritizing M4A, then any audio.
    """
    return "bestaudio[ext=m4a]/bestaudio/best"


def build_video_format_string(target_res: int) -> str:
    """Build yt-dlp format selection with resolution limit.

    Uses 4-tier fallback: AVC+M4A → any video+audio → best MP4 → best.

    Args:
        target_res: Maximum height in pixels (e.g. 1080).

    Returns:
        Format string for yt-dlp.
    """
    return (
        f"bestvideo[ext=mp4][vcodec^=avc][height<={target_res}]+bestaudio[ext=m4a]/"
        f"bestvideo[height<={target_res}]+bestaudio/"
        f"best[ext=mp4][height<={target_res}]/"
        f"best[height<={target_res}]"
    )


def build_ytdl_options(
    mode: str,
    target_res: int,
    video_format: str,
    output_dir: Path,
    bin_dir: Path,
) -> dict[str, object]:
    """Build complete yt-dlp options dict.

    Args:
        mode: "audio" or "video".
        target_res: Target resolution height (e.g. 1080).
        video_format: Video container (mp4).
        output_dir: Directory for temporary downloads.
        bin_dir: Directory containing ffmpeg binary (workspace/bin).

    Returns:
        Dict of yt-dlp options.
    """
    if mode == "audio":
        format_string = build_audio_format_string()
    else:
        format_string = build_video_format_string(target_res)

    return {
        "format": format_string,
        "http_headers": {"User-Agent": USER_AGENT},
        "merge_output_format": video_format,
        "outtmpl": str(output_dir / "source.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "logger": YTDLLogger(),
        "js_runtimes": {"bun": {}},
        "remote_components": ["ejs:github"],
        "extractor_args": {"youtube": ["player_client=ios,android,web"]},
        "overwrites": True,
        "ffmpeg_location": str(
            get_ffmpeg_path(bin_dir).parent if get_ffmpeg_path(bin_dir) else bin_dir
        ),
    }
