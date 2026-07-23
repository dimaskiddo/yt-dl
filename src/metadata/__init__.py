"""Audio metadata extraction, online search, and ID3 tag injection."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from src.core.config import MetadataConfig
from src.core.exceptions import MetadataError as MetadataError


class TrackMetadata(BaseModel):
    """Track metadata for ID3 tagging."""

    title: str = ""
    artist: str = ""
    album: str = ""
    year: str = ""  # YYYY only
    cover_data: bytes | None = None
    cover_mime: str = ""  # "image/jpeg" or "image/png"


def _dispatch_provider(provider: str, title: str, artist: str, timeout: float, config: MetadataConfig) -> dict[str, str] | None:  # noqa: E501
    """Call single metadata provider. Lazy-imports module on first call."""
    if provider == "itunes":
        from src.metadata.itunes import itunes_search
        return itunes_search(title, artist, timeout)
    if provider == "musicbrainz":
        from src.metadata.musicbrainz import musicbrainz_search
        return musicbrainz_search(title, artist, timeout)
    if provider == "spotify":
        from src.metadata.spotify import spotify_search
        return spotify_search(title, artist, timeout, config.providers.spotify.client_id, config.providers.spotify.client_secret)
    if provider == "lastfm":
        from src.metadata.lastfm import lastfm_search
        return lastfm_search(title, artist, timeout, config.providers.lastfm.api_key, config.providers.lastfm.api_secret)
    logger.debug("Unknown metadata provider: {}", provider)
    return None


def search_metadata_online(
    meta: TrackMetadata, timeout: float, config: MetadataConfig
) -> tuple[TrackMetadata | None, str]:
    """Enrich metadata via ordered provider chain. First match wins."""
    title = meta.title
    artist = meta.artist
    if not title:
        return None, ""
    provider_count = len(config.provider_order) if config.provider_order else 4
    per_timeout = timeout / max(provider_count, 1)
    for provider in config.provider_order:
        result = _dispatch_provider(provider, title, artist, per_timeout, config)
        if result:
            if result.get("title"):
                meta.title = result["title"]
            if result.get("artist"):
                meta.artist = result["artist"]
            if result.get("album"):
                meta.album = result["album"]
            if result.get("year"):
                meta.year = result["year"]
            return meta, result.get("cover_url", "")
    return None, ""


def _resolve_cover(
    meta: TrackMetadata,
    ydl_info: dict[str, object],
    config: MetadataConfig,
    online_cover_url: str = "",
) -> None:
    """Resolve cover: yt-dlp thumbnail -> online result -> default fallback."""
    from src.metadata.cover import download_cover_image, load_default_cover
    if config.force_default_cover:
        try:
            fallback = load_default_cover(config.default_cover_path)
            if fallback:
                meta.cover_data, meta.cover_mime = fallback
        except OSError:
            logger.debug("Default cover image not found at {}", config.default_cover_path)
        return
    # Priority: yt-dlp thumbnail -> online search cover -> default
    thumbnail_url = str(ydl_info.get("thumbnail", ""))
    cover_url = thumbnail_url or online_cover_url
    if cover_url:
        try:
            result = download_cover_image(cover_url, 5.0)
            if result:
                meta.cover_data, meta.cover_mime = result
                return
        except Exception:
            logger.debug("Cover download failed for {}", cover_url)
    try:
        fallback = load_default_cover(config.default_cover_path)
        if fallback:
            meta.cover_data, meta.cover_mime = fallback
    except OSError:
        pass


def inject_metadata(
    file_path: Path,
    ydl_info: dict[str, object],
    audio_format: str,
    config: MetadataConfig,
) -> None:
    """Extract, enrich, and inject ID3 tags into audio file. Non-fatal."""
    from src.metadata.tagger import tag_audio_file
    from src.metadata.ydl import extract_metadata_from_ydl
    try:
        meta = extract_metadata_from_ydl(ydl_info)
    except Exception:
        logger.warning("Failed to extract yt-dlp metadata")
        return
    online_cover_url = ""
    if config.online_search and meta.title:
        try:
            enriched, online_cover_url = search_metadata_online(meta, config.online_timeout, config)
            if enriched:
                meta = enriched
                logger.debug("Metadata enriched via online search")
        except Exception:
            logger.debug("Online metadata search failed")
    _resolve_cover(meta, ydl_info, config, online_cover_url)
    try:
        tag_audio_file(file_path, meta, audio_format)
        logger.info("ID3 tags written for {}", file_path.name)
    except Exception:
        logger.warning("Failed to write ID3 tags for {}", file_path.name)
