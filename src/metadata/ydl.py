"""yt-dlp info dict metadata extraction."""

from __future__ import annotations

from src.metadata import TrackMetadata


def extract_metadata_from_ydl(info: dict[str, object]) -> TrackMetadata:
    """Extract metadata from yt-dlp info dict.

    Args:
        info: Raw info dict from yt_dlp.YoutubeDL.extract_info().

    Returns:
        TrackMetadata with available fields.
    """
    title = str(info.get("title", ""))
    uploader = str(info.get("uploader", ""))
    upload_date = str(info.get("upload_date", ""))

    # YYYYMMDD -> YYYY (year only)
    year = ""
    if len(upload_date) >= 4 and upload_date[:4].isdigit():
        year = upload_date[:4]

    return TrackMetadata(title=title, artist=uploader, year=year)
