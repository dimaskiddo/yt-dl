"""Download command — download and process YouTube videos."""

from __future__ import annotations

import typer

from src.core.config import get_config
from src.core.utils import format_bytes, validate_youtube_url
from src.downloader.downloader import DownloadRequest, VideoDownloader


def download_cmd(
    url: str = typer.Argument(help="YouTube URL to download"),
    mode: str = typer.Option(
        "video", "--mode", "-m", help="Download mode: audio or video"
    ),
    bitrate: str = typer.Option(
        "192K", "--bitrate", "-b", help="Audio bitrate: 128K, 192K, 256K, 320K"
    ),
    audio_format: str = typer.Option(
        "mp3", "--format", "-f", help="Audio format: mp3, aac, opus"
    ),
    resolution: str = typer.Option(
        "720p", "--resolution", "-r", help="Video resolution: 360p-1440p"
    ),
    force: bool = typer.Option(False, "--force", help="Re-download even if cached"),
) -> None:
    """Download a YouTube video as audio or video.

    Args:
        url: YouTube URL to download.
        mode: Download mode (audio or video).
        bitrate: Audio bitrate.
        audio_format: Audio format (mp3, aac, opus).
        resolution: Video resolution.
        force: Re-download even if cached.

    Raises:
        typer.Exit: On download failure.
    """
    config = get_config()
    url = validate_youtube_url(url)

    request = DownloadRequest(
        url=url,
        mode=mode,
        audio_bitrate=bitrate,
        audio_format=audio_format,
        video_resolution=resolution,
        video_format=config.downloader.video_format,
    )

    downloader = VideoDownloader(config)

    try:
        result = downloader.download(request, force=force)
        typer.echo("")
        size = format_bytes(
            result.output_path.stat().st_size if result.output_path.exists() else 0
        )
        typer.echo(f"✓ {result.output_path.name} ({size})")
        if result.metadata:
            if result.metadata.get("title"):
                typer.echo(f"   Title : {result.metadata['title']}")
            if result.metadata.get("artist"):
                typer.echo(f"   Artist: {result.metadata['artist']}")
    except Exception as e:
        typer.echo("")
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(1) from None


def register(cli: typer.Typer) -> None:
    """Register download command with CLI app."""
    cli.command("download")(download_cmd)
