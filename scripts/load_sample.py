"""Create the persistent collection and upsert a 40-track sample."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from findmusic.corpus import INSPECTED_TRACK_IDS, load_songs, select_sample
from findmusic.store import open_collection, upsert_songs


def main() -> None:
    songs = load_songs(ROOT)
    sample = select_sample(songs)
    collection = open_collection(ROOT)
    before = collection.count()
    upsert_songs(collection, sample)
    after = collection.count()

    embedding = collection._embedding_function
    truncated = 0
    if embedding is not None:
        for song in sample:
            encoded = embedding.tokenizer.encode(song.document)
            if encoded.overflowing:
                truncated += 1

    print(f"corpus_tracks={len(songs)}")
    print(f"sample_tracks={len(sample)}")
    print(f"count_before={before}")
    print(f"count_after={after}")
    print(f"documents_truncated_at_256_tokens={truncated}")
    print(f"collection={collection.name}")
    print(f"persist_dir={ROOT / 'data' / 'chroma'}")
    inspected = ", ".join(str(track_id) for track_id in INSPECTED_TRACK_IDS)
    print(f"inspected_track_ids={inspected}")
    filler = [song for song in sample if song.track_id not in INSPECTED_TRACK_IDS]
    print(
        "filler_track_id_range="
        f"{filler[0].track_id}-{filler[-1].track_id} ({len(filler)} tracks)"
    )
    for song in sample:
        if song.track_id in INSPECTED_TRACK_IDS:
            print(f"included\t{song.record_id}\t{song.title}\t{song.artist}")


if __name__ == "__main__":
    main()
