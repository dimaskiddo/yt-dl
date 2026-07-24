"""Format-specific ID3 tag writers — MP3, AAC, OPUS."""

from __future__ import annotations

import base64
from pathlib import Path

from loguru import logger

from src.metadata import MetadataError, TrackMetadata


def _tag_mp3(file_path: Path, meta: TrackMetadata) -> None:
    """Write ID3v2.4 tags to MP3 file."""
    from mutagen.id3 import APIC, ID3, TALB, TDRC, TIT2, TPE1, TPE2

    tags = ID3()
    if meta.title:
        tags.add(TIT2(encoding=3, text=meta.title))
    if meta.artist:
        tags.add(TPE1(encoding=3, text=meta.artist))
        tags.add(TPE2(encoding=3, text=meta.artist))
    if meta.album:
        tags.add(TALB(encoding=3, text=meta.album))
    if meta.year:
        tags.add(TDRC(encoding=3, text=meta.year))
    if meta.cover_data and meta.cover_mime:
        tags.add(
            APIC(
                encoding=3,
                mime=meta.cover_mime,
                type=3,
                desc="Cover",
                data=meta.cover_data,
            )
        )

    tags.save(str(file_path), v2_version=4)


def _tag_aac(file_path: Path, meta: TrackMetadata) -> None:
    """Write iTunes-style metadata atoms to AAC/MP4 file."""
    from mutagen.mp4 import MP4, MP4Cover

    audio = MP4(str(file_path))
    if meta.title:
        audio["\xa9nam"] = meta.title
    if meta.artist:
        audio["\xa9ART"] = meta.artist
    if meta.album:
        audio["\xa9alb"] = meta.album
    if meta.year:
        audio["\xa9day"] = meta.year
    if meta.cover_data and meta.cover_mime:
        fmt = MP4Cover.FORMAT_JPEG if "jpeg" in meta.cover_mime else MP4Cover.FORMAT_PNG
        audio["covr"] = [MP4Cover(meta.cover_data, imageformat=fmt)]

    audio.save()


def _tag_opus(file_path: Path, meta: TrackMetadata) -> None:
    """Write VorbisComment tags to OPUS file."""
    from mutagen.flac import Picture
    from mutagen.oggopus import OggOpus

    audio = OggOpus(str(file_path))
    if meta.title:
        audio["title"] = meta.title
    if meta.artist:
        audio["artist"] = meta.artist
    if meta.album:
        audio["album"] = meta.album
    if meta.year:
        audio["date"] = meta.year
    if meta.cover_data and meta.cover_mime:
        pic = Picture()
        pic.type = 3  # Cover (front)
        pic.mime = meta.cover_mime
        pic.desc = "Cover"
        pic.data = meta.cover_data
        audio["metadata_block_picture"] = base64.b64encode(pic.write()).decode("ascii")

    audio.save()


def tag_audio_file(file_path: Path, meta: TrackMetadata, audio_format: str) -> None:
    """Write metadata tags to audio file based on format.

    Args:
        file_path: Path to audio file.
        meta: Track metadata.
        audio_format: Format string (mp3, aac, opus).

    Raises:
        MetadataError: If file not found or format unsupported.
    """
    if not file_path.is_file():
        raise MetadataError(f"Audio file not found: {file_path}")

    tag_type = _tag_map().get(audio_format)
    if tag_type is None:
        raise MetadataError(f"Unsupported audio format for tagging: {audio_format}")

    if tag_type == "mp3":
        _tag_mp3(file_path, meta)
    elif tag_type == "aac":
        _tag_aac(file_path, meta)
    elif tag_type == "opus":
        _tag_opus(file_path, meta)

    logger.debug(
        "ID3 tags written to {} (title={}, artist={}, album={})",
        file_path.name,
        meta.title,
        meta.artist,
        meta.album,
    )


def _tag_map() -> dict[str, str]:
    """Map audio format strings to tagger type identifiers."""
    return {"mp3": "mp3", "aac": "aac", "opus": "opus"}
