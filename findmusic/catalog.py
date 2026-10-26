"""Validate and store a song added while the app is running."""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import quote

from chromadb.api.models.Collection import Collection

TRACK_URL = re.compile(
    r"^https://open\.spotify\.com/(?:intl-[a-z]{2}/)?track/([A-Za-z0-9]{22})(?:\?.*)?$"
)


class SongRejected(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.status_code = status_code


def add_song(
    collection: Collection,
    *,
    title: str,
    artist: str,
    description: str,
    tags: str = "",
    spotify_url: str = "",
) -> dict[str, Any]:
    clean_title = _required(title, "Title", 200)
    clean_artist = _required(artist, "Artist", 200)
    clean_description = _required(description, "Description", 4000)
    if len(clean_description) < 20:
        raise SongRejected("Write a descriptive paragraph of at least 20 characters.")

    tag_list = _tags(tags)
    track_url = _track_url(spotify_url)
    record_id = _record_id(clean_title, clean_artist)
    if _already_stored(collection, record_id, clean_title, clean_artist):
        raise SongRejected(
            "A song with this title and artist is already stored.",
            status_code=409,
        )

    document = clean_description
    tag_line = ", ".join(tag_list)
    if tag_line:
        document = f"{document}\n\nTags: {tag_line}"
    search_query = quote(f"{clean_title} {clean_artist}", safe="")
    collection.upsert(
        ids=[record_id],
        documents=[document],
        metadatas=[
            {
                "track_id": record_id,
                "title": clean_title,
                "artist": clean_artist,
                "album": "",
                "tags": tag_line,
                "source": "user",
                "source_url": "",
                "spotify_track_url": track_url,
                "spotify_search_url": f"https://open.spotify.com/search/{search_query}",
                "caption_count": 1,
                "has_validated_caption": False,
            }
        ],
    )
    return {
        "id": record_id,
        "title": clean_title,
        "artist": clean_artist,
        "spotify_verified": bool(track_url),
    }


def _required(value: str, label: str, limit: int) -> str:
    text = " ".join(str(value or "").split())
    if not text:
        raise SongRejected(f"{label} is required.")
    if len(text) > limit:
        raise SongRejected(f"{label} must be {limit} characters or fewer.")
    return text


def _tags(value: str) -> list[str]:
    text = str(value or "").strip()
    if len(text) > 300:
        raise SongRejected("Tags must be 300 characters or fewer.")
    tags = []
    for part in text.split(","):
        tag = " ".join(part.split())
        if tag and tag not in tags:
            tags.append(tag)
    if len(tags) > 12:
        raise SongRejected("Enter at most 12 tags.")
    return tags


def _track_url(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    match = TRACK_URL.fullmatch(text)
    if match is None:
        raise SongRejected(
            "Spotify link must be a track URL such as "
            "https://open.spotify.com/track/... Leave it blank to use a search link."
        )
    return f"https://open.spotify.com/track/{match.group(1)}"


def _record_id(title: str, artist: str) -> str:
    key = f"{title.casefold()}|{artist.casefold()}"
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
    return f"user-{digest}"


def _already_stored(collection: Collection, record_id: str, title: str, artist: str) -> bool:
    existing = collection.get(ids=[record_id])
    if existing.get("ids"):
        return True
    needle = {_norm(title), _norm(f"{title} {artist}")}
    stored = collection.get(include=["metadatas"], limit=collection.count())
    for metadata in stored.get("metadatas") or []:
        if metadata is None:
            continue
        names = {
            _norm(str(metadata.get("title", ""))),
            _norm(f"{metadata.get('title', '')} {metadata.get('artist', '')}"),
        }
        if needle & names and _norm(str(metadata.get("artist", ""))) == _norm(artist):
            return True
    return False


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())
