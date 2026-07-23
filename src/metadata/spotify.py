"""Spotify Web API provider (Client Credentials OAuth)."""

from __future__ import annotations

import base64
import json
import urllib.parse
import urllib.request

from loguru import logger

from src.core.constants import USER_AGENT
from src.metadata.utils import _http_get_json


def _spotify_auth(
    client_id: str, client_secret: str, timeout: float
) -> str | None:
    """Obtain Spotify access token via Client Credentials flow."""
    try:
        auth = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=b"grant_type=client_credentials",
            headers={
                "Authorization": f"Basic {auth}",
                "Content-Type": "application/x-www-form-urlencoded",
                "User-Agent": USER_AGENT,
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            token_data = json.loads(resp.read().decode("utf-8"))
        return token_data.get("access_token", "") or None
    except Exception:
        logger.debug("Spotify auth failed")
        return None


def spotify_search(
    title: str,
    artist: str,
    timeout: float,
    client_id: str,
    client_secret: str,
) -> dict[str, str] | None:
    """Search Spotify API for track metadata. Uses Client Credentials flow."""
    if not client_id or not client_secret:
        return None
    access_token = _spotify_auth(client_id, client_secret, timeout / 2)
    if not access_token:
        return None
    query = urllib.parse.quote(f"track:{title} artist:{artist}")
    url = f"https://api.spotify.com/v1/search?q={query}&type=track&limit=1"
    data = _http_get_json(url, timeout / 2, headers={"Authorization": f"Bearer {access_token}"})
    if not data:
        return None
    tracks = data.get("tracks", {}).get("items", [])
    if not tracks:
        return None
    track = tracks[0]
    album = track.get("album", {})
    images = album.get("images", [])
    cover_url = images[0]["url"] if images else ""
    artists = track.get("artists", [])
    artist_name = artists[0]["name"] if artists else ""
    year = ""
    release_date = album.get("release_date", "")
    if len(release_date) >= 4 and release_date[:4].isdigit():
        year = release_date[:4]
    return {
        "title": track.get("name", ""),
        "artist": artist_name,
        "album": album.get("name", ""),
        "year": year,
        "cover_url": cover_url,
    }
