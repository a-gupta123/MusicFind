"""Query an existing collection. This script does not upsert records."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from findmusic.store import open_collection

DEFAULT_QUERIES = ("slow solo piano with reverb",)


def main() -> None:
    parser = argparse.ArgumentParser(description="Query the persisted song sample.")
    parser.add_argument("queries", nargs="*", default=list(DEFAULT_QUERIES))
    parser.add_argument("--n-results", type=int, default=3)
    parser.add_argument("--record-id", default="jamendo-1116406")
    args = parser.parse_args()

    collection = open_collection(ROOT)
    print(f"count={collection.count()}")
    print(f"collection_metadata={collection.metadata}")

    stored = collection.get(ids=[args.record_id], include=["documents", "metadatas"])
    ids = stored.get("ids") or []
    if not ids:
        raise SystemExit(f"Missing persisted record {args.record_id}")
    document = stored["documents"][0]
    metadata = stored["metadatas"][0]
    digest = hashlib.sha256(document.encode("utf-8")).hexdigest()
    print(f"stored_id={ids[0]}")
    print(f"stored_title={metadata['title']}")
    print(f"stored_artist={metadata['artist']}")
    print(f"stored_spotify_track_url={metadata['spotify_track_url']!r}")
    print(f"stored_spotify_search_url={metadata['spotify_search_url']}")
    print(f"stored_document_sha256={digest}")
    print(f"stored_document={document}")

    for query in args.queries:
        print(f"\nQUERY {query}")
        result = collection.query(query_texts=[query], n_results=args.n_results)
        for rank, (record_id, distance, meta, text) in enumerate(
            zip(
                result["ids"][0],
                result["distances"][0],
                result["metadatas"][0],
                result["documents"][0],
            ),
            start=1,
        ):
            print(f"#{rank}\tdistance={distance:.4f}\tid={record_id}")
            print(f"    {meta['title']} — {meta['artist']}")
            preview = text.replace("\n", " ")
            if len(preview) > 240:
                preview = preview[:240] + "..."
            print(f"    {preview}")


if __name__ == "__main__":
    main()
