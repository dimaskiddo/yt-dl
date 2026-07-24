"""iTunes Search API provider."""

from __future__ import annotations

import urllib.parse

from src.metadata.utils import _http_get_json


def itunes_search(title: str, artist: str, timeout: float) -> dict[str, str] | None:
    """Search iTunes API for track metadata."""
    query = urllib.parse.quote(f"{title} {artist}")
    url = f"https://itunes.apple.com/search?term={query}&entity=song&limit=1"
    data = _http_get_json(url, timeout)
    if not data:
        return None
    results = data.get("results", [])
    if not results:
        return None
    track = results[0]
    cover_url = track.get("artworkUrl100", "")
    if cover_url:
        cover_url = cover_url.replace("100x100bb", "1000x1000bb")
    year = ""
    release_date = track.get("releaseDate", "")
    if len(release_date) >= 4 and release_date[:4].isdigit():
        year = release_date[:4]
    return {
        "title": track.get("trackName", ""),
        "artist": track.get("artistName", ""),
        "album": track.get("collectionName", ""),
        "year": year,
        "cover_url": cover_url,
    }
