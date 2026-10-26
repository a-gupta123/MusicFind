"""Run saved queries against the persisted collection and show word overlap."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from findmusic.store import open_collection

# Product examples, plus paraphrase attempts whose important words may be
# absent from a relevant caption. Results are not assumed here.
QUERIES = (
    "Dreamy late-night music with soft vocals and lots of reverb",
    "Jazz piano for studying on a rainy afternoon",
    "Songs with a similar atmosphere to Frank Ocean",
    "Energetic guitar music for walking to class",
    "Melancholy instrumental music that gradually builds",
    "slow solo piano with reverb",
    "a keyboard piece that sounds like it was recorded in a large empty room",
    "wordless music that grows heavier as it goes on",
    "quiet background music for reading",
    "music to drift off to sleep",
    "songs that make me drowsy",
)

WORD = re.compile(r"[a-z0-9']+")


def content_words(text: str) -> set[str]:
    return {word for word in WORD.findall(text.lower()) if len(word) >= 4}


def main() -> None:
    collection = open_collection(ROOT)
    print(f"count={collection.count()}")
    for query in QUERIES:
        print(f"\nQUERY {query}")
        query_words = content_words(query)
        result = collection.query(query_texts=[query], n_results=5)
        for rank, (record_id, distance, meta, text) in enumerate(
            zip(
                result["ids"][0],
                result["distances"][0],
                result["metadatas"][0],
                result["documents"][0],
            ),
            start=1,
        ):
            document_words = content_words(text)
            present = sorted(query_words & document_words)
            missing = sorted(query_words - document_words)
            print(f"#{rank}\tdistance={distance:.4f}\tid={record_id}")
            print(f"    {meta['title']} — {meta['artist']}")
            print(f"    query_words_present={present}")
            print(f"    query_words_missing={missing}")
            preview = " ".join(text.split())
            if len(preview) > 500:
                preview = preview[:500] + "..."
            print(f"    {preview}")


if __name__ == "__main__":
    main()
