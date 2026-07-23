"""Last.fm API provider."""

from __future__ import annotations

import urllib.parse

from src.metadata.utils import _http_get_json


def lastfm_search(
    title: str, artist: str, timeout: float, api_key: str, _api_secret: str = ""
) -> dict[str, str] | None:
    """Search Last.fm API for track metadata."""
    if not api_key:
        return None
    track_q = urllib.parse.quote(title)
    artist_q = urllib.parse.quote(artist)
    url = (
        "https://ws.audioscrobbler.com/2.0/?"
        f"method=track.search&track={track_q}&artist={artist_q}"
        f"&api_key={api_key}&format=json&limit=1"
    )
    data = _http_get_json(url, timeout)
    if not data:
        return None
    results = data.get("results", {})
    matches = results.get("trackmatches", {}).get("track", [])
    if not matches:
        return None
    track = matches[0]
    # Largest image: mega > extralarge > large > medium > small
    images = track.get("image", [])
    cover_url = ""
    for img in reversed(images):
        if img.get("#text"):
            cover_url = img["#text"]
            break
    return {
        "title": track.get("name", ""),
        "artist": track.get("artist", ""),
        "album": "",  # track.search has no album
        "year": "",  # track.search has no date
        "cover_url": cover_url,
    }
