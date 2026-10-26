"""FastAPI app for search and adding a song."""

from __future__ import annotations

import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from findmusic.catalog import SongRejected, add_song
from findmusic.corpus import load_songs
from findmusic.paths import app_root, prepare_embedding_cache
from findmusic.retrieve import search_songs
from findmusic.store import open_collection, upsert_songs

logger = logging.getLogger("findmusic")
STATIC_DIR = Path(__file__).resolve().parents[1] / "static"
BATCH_SIZE = 100

_lock = threading.Lock()
_state: dict[str, object] = {
    "ready": False,
    "persistent": True,
    "count": 0,
    "collection": None,
    "root": None,
}


class SongInput(BaseModel):
    title: str = ""
    artist: str = ""
    description: str = ""
    tags: str = ""
    spotify_url: str = Field(default="", max_length=300)


def ensure_ready() -> dict[str, object]:
    if _state["ready"]:
        return _state
    with _lock:
        if _state["ready"]:
            return _state
        root = app_root()
        prepare_embedding_cache()
        logger.info("Opening collection at %s", root)
        songs = load_songs(root)
        collection = open_collection(root)
        if collection.count() < len(songs):
            logger.info("Loading %s songs into the collection", len(songs))
            for start in range(0, len(songs), BATCH_SIZE):
                upsert_songs(collection, songs[start : start + BATCH_SIZE])
        _state.update(
            ready=True,
            persistent=not str(root).startswith("/tmp"),
            count=collection.count(),
            collection=collection,
            root=root,
        )
        logger.info("Collection ready with %s songs", _state["count"])
        return _state


app = FastAPI(title="FindMusic")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def home() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, object]:
    state = ensure_ready()
    collection = state["collection"]
    count = collection.count() if collection is not None else 0
    state["count"] = count
    return {
        "ready": True,
        "count": count,
        "persistent": bool(state["persistent"]),
    }


@app.get("/api/search")
def search(q: str = "") -> dict[str, object]:
    state = ensure_ready()
    try:
        with _lock:
            return search_songs(state["collection"], q)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/songs")
def create_song(song: SongInput) -> dict[str, object]:
    state = ensure_ready()
    try:
        with _lock:
            created = add_song(
                state["collection"],
                title=song.title,
                artist=song.artist,
                description=song.description,
                tags=song.tags,
                spotify_url=song.spotify_url,
            )
            state["count"] = state["collection"].count()
            return created
    except SongRejected as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from error
