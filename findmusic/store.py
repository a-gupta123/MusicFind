"""Local persistent Chroma collection for song descriptions."""

from __future__ import annotations

import os
from pathlib import Path

# Chroma reads this on import. Leave an explicit user setting alone.
os.environ.setdefault("ANONYMIZED_TELEMETRY", "False")

import chromadb
from chromadb.api.models.Collection import Collection
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from findmusic.corpus import SOURCE_DOI, SOURCE_LICENSE, SOURCE_NAME, Song

COLLECTION_NAME = "songs"


def persist_dir(root: Path) -> Path:
    return root / "data" / "chroma"


def open_collection(root: Path) -> Collection:
    path = persist_dir(root)
    path.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(path))
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        configuration={"hnsw": {"space": "cosine"}},
        embedding_function=ONNXMiniLM_L6_V2(),
        metadata={
            "source": SOURCE_NAME,
            "license": SOURCE_LICENSE,
            "doi": SOURCE_DOI,
        },
    )


def upsert_songs(collection: Collection, songs: list[Song]) -> None:
    if not songs:
        return
    collection.upsert(
        ids=[song.record_id for song in songs],
        documents=[song.document for song in songs],
        metadatas=[song.metadata() for song in songs],
    )
