"""MusicBrainz API provider."""

from __future__ import annotations

import urllib.parse

from src.metadata.utils import _http_get_json


def musicbrainz_search(
    title: str, artist: str, timeout: float
) -> dict[str, str] | None:
    """Search MusicBrainz API for recording metadata."""
    query = urllib.parse.quote(f'recording:"{title}" AND artist:"{artist}"')
    url = f"https://musicbrainz.org/ws/2/recording/?query={query}&fmt=json&limit=1"
    data = _http_get_json(url, timeout)
    if not data:
        return None
    recordings = data.get("recordings", [])
    if not recordings:
        return None
    rec = recordings[0]
    artist_name = ""
    artist_credit = rec.get("artist-credit", [])
    if artist_credit:
        artist_name = artist_credit[0].get("name", "")
    album = ""
    releases = rec.get("releases", [])
    if releases:
        album = releases[0].get("title", "")
    year = ""
    first_date = rec.get("first-release-date", "")
    if len(first_date) >= 4 and first_date[:4].isdigit():
        year = first_date[:4]
    return {
        "title": rec.get("title", ""),
        "artist": artist_name,
        "album": album,
        "year": year,
    }
