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


def _build_video_cmd(
    input_path: Path,
    output_path: Path,
    resolution_height: int,
    ffmpeg_path: str,
) -> list[str]:
    """Build FFmpeg video encoding command.

    Args:
        input_path: Source file path.
        output_path: Target video file path.
        resolution_height: Target resolution height in pixels.
        ffmpeg_path: Path to ffmpeg binary.

    Returns:
        Complete FFmpeg command list.
    """
    return [
        ffmpeg_path,
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        "libx264",
        "-crf",
        "23",
        "-preset",
        "medium",
        "-vf",
        f"scale=-2:{resolution_height}",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        str(output_path),
    ]


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


def encode_video(
    input_path: Path,
    output_path: Path,
    resolution_height: int,
    ffmpeg_path: str,
    video_id: str = "",
    video_format: str = "mp4",
    timeout: int = 3600,
) -> Path:
    """Re-encode video for better compression at same quality.

    Uses H.264 CRF encoding for efficient file size while maintaining quality.

    Args:
        input_path: Source file path.
        output_path: Target video file path.
        resolution_height: Target resolution height in pixels (e.g. 1080).
        ffmpeg_path: Path to ffmpeg binary.
        video_id: YouTube video ID for log context.
        video_format: Target video format (e.g. "mp4").
        timeout: Timeout in seconds.

    Returns:
        Path to encoded video file.

    Raises:
        FFmpegError: If FFmpeg fails.
    """
    cmd = _build_video_cmd(input_path, output_path, resolution_height, ffmpeg_path)

    logger.info(
        "Encoding video for {} to {} {}p...",
        video_id.upper(),
        video_format.upper(),
        resolution_height,
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
