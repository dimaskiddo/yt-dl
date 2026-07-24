"""Download orchestrator — yt-dlp invocation, retry logic, FFmpeg processing."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from src.core.config import AppConfig
from src.core.constants import WORKSPACE_TMP
from src.core.exceptions import DownloadError
from src.core.utils import extract_video_id, parse_resolution_height
from src.core.workspace import ACTIVE_DOWNLOAD_EVENT, get_ffmpeg_path
from src.downloader.ffmpeg_processor import encode_audio, stream_copy_video
from src.downloader.yt_dlp_config import build_ytdl_options


class DownloadRequest(BaseModel):
    """Download request parameters."""

    url: str
    mode: str
    audio_bitrate: str = "192K"
    audio_format: str = "mp3"
    video_resolution: str = "1080p"
    video_format: str = "mp4"


class DownloadResult(BaseModel):
    """Download result data."""

    video_id: str
    video_title: str = ""
    output_path: Path
    status: str = "complete"
    metadata: dict[str, str] = {}


# Transient error patterns (download may succeed on retry)
_TRANSIENT_CLASSES: frozenset[str] = frozenset(
    {
        "URLError",
        "HTTPError",
        "TimeoutError",
        "SocketTimeout",
        "socket.timeout",
        "ConnectionError",
        "ConnectionResetError",
        "ConnectionAbortedError",
        "ConnectionRefusedError",
        "IncompleteRead",
        "HTTPException",
        "FileNotFoundError",
    }
)

_TRANSIENT_PATTERNS: tuple[str, ...] = (
    "http error 4",
    "too many requests",
    "connection",
    "timeout",
    "timed out",
    "incompleteread",
    "try again",
    "temporary failure",
    "429",
    "read timed out",
    "no such file",
)

_PERMANENT_PATTERNS: tuple[str, ...] = (
    "unplayable",
    "private",
    "removed",
    "copyright",
    "geo-block",
    "geoblock",
    "sign in",
)


def _is_transient(exc: Exception) -> bool:
    """Check if an exception is transient and worth retrying.

    Args:
        exc: Exception to classify.

    Returns:
        True if the error is likely temporary.
    """
    # Phase 1: exception class name check
    exc_name = type(exc).__name__
    if exc_name in _TRANSIENT_CLASSES:
        return True

    # Phase 2: message pattern check
    msg = str(exc).lower()
    for pattern in _TRANSIENT_PATTERNS:
        if pattern in msg:
            return all(permanent not in msg for permanent in _PERMANENT_PATTERNS)

    return False


class VideoDownloader:
    """Main download orchestrator."""

    def __init__(
        self,
        config: AppConfig,
    ) -> None:
        """Initialize downloader.

        Args:
            config: Application config.
        """
        self.config = config
        self._source_path: Path | None = None

    def download(
        self,
        request: DownloadRequest,
        force: bool = False,
    ) -> DownloadResult:
        """Download and process a YouTube video.

        Args:
            request: Download request with URL and format options.
            force: Re-download even if cached.

        Returns:
            DownloadResult with output path and status.

        Raises:
            DownloadError: If download or processing fails.
        """
        video_id = extract_video_id(request.url)
        output_path = self._build_output_path(video_id, request)
        log_path = str(output_path.relative_to(Path("workspace")))

        if output_path.exists() and not force:
            vid = video_id.upper()
            if request.mode == "audio":
                logger.info(
                    "Using cached audio for {} {} {}",
                    vid,
                    request.audio_format.upper(),
                    request.audio_bitrate,
                )
            else:
                logger.info(
                    "Using cached video for {} {} {}",
                    vid,
                    request.video_format.upper(),
                    request.video_resolution,
                )
            return DownloadResult(
                video_id=video_id, output_path=output_path, status="cached"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        title, ydl_info = self._download_and_process(video_id, output_path, request)

        meta_summary: dict[str, str] = {}
        if request.mode == "audio" and ydl_info:
            meta_summary = {
                "title": title,
                "artist": str(ydl_info.get("uploader", "")),
            }

        logger.info("Files saved to {}", log_path)
        return DownloadResult(
            video_id=video_id,
            video_title=title,
            output_path=output_path,
            metadata=meta_summary,
        )

    def _download_and_process(
        self,
        video_id: str,
        output_path: Path,
        request: DownloadRequest,
    ) -> tuple[str, dict[str, object]]:
        """Download, process, and move to final output.

        Args:
            video_id: YouTube video ID.
            output_path: Final output path.
            request: Download request.

        Returns:
            Tuple of (video_title, yt-dlp info dict).

        Raises:
            DownloadError: If download or processing fails.
        """
        staging_dir = WORKSPACE_TMP / video_id
        staging_dir.mkdir(parents=True, exist_ok=True)
        log_path = str(output_path.relative_to(Path("workspace")))

        ACTIVE_DOWNLOAD_EVENT.set()
        try:
            try:
                target_res = parse_resolution_height(request.video_resolution)
                opts = build_ytdl_options(
                    mode=request.mode,
                    target_res=target_res,
                    video_format=request.video_format,
                    output_dir=staging_dir,
                    bin_dir=self.config.workspace.bin,
                )
                ydl_info = self._download_with_retry(
                    request.url, opts, video_id=video_id, mode=request.mode
                )
                title = ydl_info.get("title", "") if ydl_info else ""
            except Exception as e:
                self._cleanup_tmp(staging_dir)
                raise DownloadError(f"Download failed: {e}") from e

            source = self._find_source(staging_dir)
            if not source:
                self._cleanup_tmp(staging_dir)
                raise DownloadError("Download completed but source file not found")

            self._source_path = source

            try:
                self._process_source(
                    source, staging_dir, output_path, request, video_id
                )
            except Exception as e:
                self._cleanup_tmp(staging_dir)
                raise DownloadError(f"Processing failed: {e}") from e

            if request.mode == "audio" and self.config.metadata.enabled:
                staging_output = staging_dir / output_path.name
                try:
                    from src.metadata import inject_metadata

                    inject_metadata(
                        staging_output,
                        ydl_info,
                        request.audio_format,
                        self.config.metadata,
                        log_path,
                    )
                except Exception as e:
                    logger.warning(
                        "Metadata injection failed for {}: {}",
                        video_id.upper(),
                        e,
                    )

            self._finalize_output(staging_dir, output_path)
            return title, ydl_info
        finally:
            ACTIVE_DOWNLOAD_EVENT.clear()

    def _finalize_output(
        self,
        staging_dir: Path,
        output_path: Path,
    ) -> None:
        """Move processed file from staging to final output path.

        Args:
            staging_dir: Staging directory containing processed file.
            output_path: Final output path.

        Raises:
            DownloadError: If processed file not found in staging.
        """
        final = self._find_final(staging_dir, output_path)
        if final is None:
            self._cleanup_tmp(staging_dir)
            raise DownloadError(
                f"FFmpeg output not found in staging — expected {output_path.name}"
            )
        if final != output_path:
            shutil.move(str(final), str(output_path))
        self._cleanup_tmp(staging_dir)

    def _build_output_path(self, video_id: str, request: DownloadRequest) -> Path:
        """Build the final output path for the download.

        Args:
            video_id: YouTube video ID.
            request: Download request.

        Returns:
            Full output file path.
        """
        base = Path("workspace") / f"{request.mode}s" / video_id.upper()

        if request.mode == "audio":
            return base / f"{request.audio_bitrate}.{request.audio_format}"
        else:
            return base / f"{request.video_resolution.upper()}.{request.video_format}"

    def _download_with_retry(
        self, url: str, opts: dict[str, object], video_id: str = "", mode: str = "video"
    ) -> dict[str, object]:
        """Download with exponential backoff retry.

        Args:
            url: YouTube URL.
            opts: yt-dlp options dict.
            video_id: YouTube video ID for log context.
            mode: Download mode (audio or video).

        Returns:
            Full yt-dlp info dict.

        Raises:
            DownloadError: If all retries exhausted or permanent error.
        """
        # Lazy import — yt-dlp is heavy
        import yt_dlp

        max_attempts = self.config.downloader.max_attempts
        delay = self.config.downloader.retry_delay

        for attempt in range(1, max_attempts + 1):
            try:
                with yt_dlp.YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(url, download=True)
                    return info
            except Exception as e:
                if attempt == max_attempts or not _is_transient(e):
                    raise DownloadError(f"Download failed: {e}") from e

                sleep_time = delay**attempt
                logger.info(
                    "Retrying download {} for {} in {}s...",
                    mode,
                    video_id.upper(),
                    int(sleep_time),
                )
                time.sleep(sleep_time)

        raise DownloadError("Download failed: all retries exhausted")

    def _find_source(self, staging_dir: Path) -> Path | None:
        """Find the downloaded source file in staging directory.

        Args:
            staging_dir: Staging directory.

        Returns:
            Path to source file, or None.
        """
        for f in staging_dir.iterdir():
            if f.is_file() and f.suffix in (".mp4", ".m4a", ".webm", ".mkv", ".opus"):
                return f
        return None

    def _find_final(self, staging_dir: Path, target: Path) -> Path | None:
        """Find the processed output file in staging directory.

        Args:
            staging_dir: Staging directory.
            target: Target output path.

        Returns:
            Path to final file, or None.
        """
        # Look for the target filename in staging
        candidate = staging_dir / target.name
        if candidate.is_file():
            return candidate

        # Any file in staging with matching extension
        for f in staging_dir.iterdir():
            if f.is_file() and f.suffix == target.suffix:
                return f

        return None

    def _process_source(
        self,
        source: Path,
        staging_dir: Path,
        output: Path,
        request: DownloadRequest,
        video_id: str = "",
    ) -> None:
        """Process downloaded source via FFmpeg.

        Args:
            source: Source file path (in staging).
            staging_dir: Staging directory for FFmpeg output.
            output: Final output path (where file will be moved).
            request: Download request.
            video_id: YouTube video ID for log context.
        """
        ffmpeg = get_ffmpeg_path(self.config.workspace.bin)
        if ffmpeg is None:
            raise DownloadError(
                "FFmpeg not found — install ffmpeg to process media files"
            )
        ffmpeg_path = str(ffmpeg)
        staging_output = staging_dir / output.name

        if request.mode == "audio":
            encode_audio(
                input_path=source,
                output_path=staging_output,
                bitrate=request.audio_bitrate,
                audio_format=request.audio_format,
                ffmpeg_path=ffmpeg_path,
                video_id=video_id,
            )
        else:
            stream_copy_video(
                input_path=source,
                output_path=staging_output,
                ffmpeg_path=ffmpeg_path,
                video_id=video_id,
            )

        if not staging_output.is_file():
            raise DownloadError(
                f"FFmpeg completed but output file not found: {staging_output.name}"
            )

    def _cleanup_tmp(self, staging_dir: Path) -> None:
        """Clean up staging directory.

        Args:
            staging_dir: Directory to remove.
        """
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
