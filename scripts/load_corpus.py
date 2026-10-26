"""Upsert every Song Describer track in batches."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

from findmusic.corpus import load_songs
from findmusic.store import open_collection, upsert_songs

BATCH_SIZE = 100


def main() -> None:
    songs = load_songs(ROOT)
    ids = [song.record_id for song in songs]
    if len(ids) != len(set(ids)):
        raise SystemExit("Duplicate track ids in the parsed corpus.")

    embedding = ONNXMiniLM_L6_V2()
    embedding._download_model_if_not_exists()
    truncated = [
        song.track_id
        for song in songs
        if embedding.tokenizer.encode(song.document).overflowing
    ]

    collection = open_collection(ROOT)
    print(f"corpus_tracks={len(songs)}")
    print(f"count_before={collection.count()}")
    print(f"documents_truncated_at_256_tokens={len(truncated)}")
    if truncated:
        print(f"truncated_track_ids={truncated}")

    for batch_number, start in enumerate(range(0, len(songs), BATCH_SIZE), start=1):
        batch = songs[start : start + BATCH_SIZE]
        upsert_songs(collection, batch)
        print(
            f"batch={batch_number} upserted={len(batch)} "
            f"count={collection.count()}"
        )

    print(f"count_after={collection.count()}")


if __name__ == "__main__":
    main()
