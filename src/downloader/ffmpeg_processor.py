"""FFmpeg subprocess wrapper for audio/video encoding."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger

from src.core.exceptions import FFmpegError


def _build_audio_codec_args(audio_format: str, bitrate: str) -> list[str]:
    """Build FFmpeg audio codec arguments.

    Args:
        audio_format: Target format (mp3, aac, opus).
        bitrate: Target bitrate (e.g. "192K").

    Returns:
        List of FFmpeg codec arguments.
    """
    codec_map: dict[str, list[str]] = {
        "mp3": ["-c:a", "libmp3lame", "-b:a", bitrate],
        "aac": ["-c:a", "aac", "-b:a", bitrate],
        "opus": ["-c:a", "libopus", "-b:a", bitrate],
    }
    return codec_map.get(audio_format, ["-c:a", "copy"])


def encode_audio(
    input_path: Path,
    output_path: Path,
    bitrate: str,
    audio_format: str,
    ffmpeg_path: str,
    video_id: str = "",
    timeout: int = 3600,
) -> Path:
    """Encode audio from video or raw source to target format.

    Args:
        input_path: Source file path.
        output_path: Target audio file path.
        bitrate: Target bitrate (e.g. "192K").
        audio_format: Target format (mp3, aac, opus).
        ffmpeg_path: Path to ffmpeg binary.
        video_id: YouTube video ID for log context.
        timeout: Timeout in seconds.

    Returns:
        Path to encoded audio file.

    Raises:
        FFmpegError: If FFmpeg fails.
    """
    codec_args = _build_audio_codec_args(audio_format, bitrate)
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-vn",
        *codec_args,
        str(output_path),
    ]

    logger.info(
        "Converting audio for {} to {} {}...",
        video_id.upper(),
        audio_format.upper(),
        bitrate,
    )
    _run_ffmpeg(cmd, timeout)
    return output_path


def stream_copy_video(
    input_path: Path,
    output_path: Path,
    ffmpeg_path: str,
    video_id: str = "",
    timeout: int = 3600,
) -> Path:
    """Remux video without re-encoding using stream copy.

    Copies video and audio streams as-is into target container.
    No quality loss, near-zero CPU usage.

    Args:
        input_path: Source file path.
        output_path: Target video file path.
        ffmpeg_path: Path to ffmpeg binary.
        video_id: YouTube video ID for log context.
        timeout: Timeout in seconds.

    Returns:
        Path to remuxed video file.

    Raises:
        FFmpegError: If FFmpeg fails.
    """
    cmd = [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-c",
        "copy",
        str(output_path),
    ]

    logger.info(
        "Stream copying video for {} (no re-encode)...",
        video_id.upper(),
    )
    _run_ffmpeg(cmd, timeout)
    return output_path


def _run_ffmpeg(
    cmd: list[str],
    timeout: int,
) -> None:
    """Execute FFmpeg command.

    Args:
        cmd: Complete FFmpeg command list.
        timeout: Timeout in seconds.

    Raises:
        FFmpegError: If FFmpeg returns non-zero exit code.
    """
    logger.debug("Running: {}", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            stderr=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise FFmpegError("FFmpeg process timed out") from None
    except FileNotFoundError:
        raise FFmpegError(f"FFmpeg not found: {cmd[0]}") from None

    if result.returncode != 0:
        stderr_output = result.stderr.decode("utf-8", errors="replace")
        raise FFmpegError(
            f"FFmpeg failed (exit {result.returncode}): {stderr_output}"
        ) from None
