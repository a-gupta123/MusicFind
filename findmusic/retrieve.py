"""Semantic search over stored songs, plus exact title and artist matches."""

from __future__ import annotations

import re
from typing import Any

from chromadb.api.models.Collection import Collection

WORD = re.compile(r"[a-z0-9']+")
STOP_WORDS = {
    "with",
    "that",
    "from",
    "this",
    "into",
    "over",
    "lots",
    "song",
    "songs",
    "music",
    "like",
    "very",
    "just",
    "some",
    "your",
    "have",
    "want",
}
RESULT_LIMIT = 5


def search_songs(collection: Collection, query: str) -> dict[str, Any]:
    text = " ".join(query.split())
    if not text:
        raise ValueError("Enter a description of what you want to hear.")

    total = collection.count()
    if total == 0:
        return {
            "query": text,
            "count": 0,
            "notice": "The collection is empty.",
            "results": [],
        }

    found = collection.query(
        query_texts=[text],
        n_results=min(RESULT_LIMIT, total),
    )
    semantic = []
    for record_id, distance, metadata, document in zip(
        found["ids"][0],
        found["distances"][0],
        found["metadatas"][0],
        found["documents"][0],
    ):
        semantic.append(
            _card(
                record_id=record_id,
                metadata=metadata,
                document=document,
                distance=float(distance),
                match="semantic",
                query=text,
            )
        )

    results = _merge_exact(collection, text, semantic)
    results = _promote_exact(text, results)
    notice = _notice(text, results)
    return {
        "query": text,
        "count": len(results),
        "notice": notice,
        "results": results,
    }


def _merge_exact(
    collection: Collection,
    query: str,
    semantic: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    needle = _norm(query)
    if len(needle) < 2:
        return semantic

    stored = collection.get(include=["metadatas", "documents"], limit=collection.count())
    seen = {card["id"] for card in semantic}
    exact = []
    ids = stored.get("ids") or []
    metadatas = stored.get("metadatas") or []
    documents = stored.get("documents") or []
    for record_id, metadata, document in zip(ids, metadatas, documents):
        if metadata is None or record_id in seen:
            continue
        names = {
            _norm(str(metadata.get("title", ""))),
            _norm(str(metadata.get("artist", ""))),
            _norm(f"{metadata.get('title', '')} {metadata.get('artist', '')}"),
            _norm(f"{metadata.get('artist', '')} {metadata.get('title', '')}"),
        }
        if needle not in names:
            continue
        exact.append(
            _card(
                record_id=record_id,
                metadata=metadata,
                document=document or "",
                distance=None,
                match="exact",
                query=query,
            )
        )
    return exact + semantic


def _promote_exact(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    needle = _norm(query)
    promoted = []
    rest = []
    for card in results:
        names = {
            _norm(card["title"]),
            _norm(card["artist"]),
            _norm(f"{card['title']} {card['artist']}"),
            _norm(f"{card['artist']} {card['title']}"),
        }
        if needle in names and card["match"] != "exact":
            explanation = card["explanation"]
            if not explanation.startswith("The title and artist match"):
                explanation = f"The title and artist match your search. {explanation}"
            promoted.append({**card, "match": "exact", "distance": None, "explanation": explanation})
        elif card["match"] == "exact":
            promoted.append(card)
        else:
            rest.append(card)
    return promoted + rest


def _card(
    *,
    record_id: str,
    metadata: dict[str, Any],
    document: str,
    distance: float | None,
    match: str,
    query: str,
) -> dict[str, Any]:
    track_url = str(metadata.get("spotify_track_url") or "")
    search_url = str(metadata.get("spotify_search_url") or "")
    verified = bool(track_url)
    tags = [part.strip() for part in str(metadata.get("tags") or "").split(",") if part.strip()]
    return {
        "id": record_id,
        "title": str(metadata.get("title") or "Untitled"),
        "artist": str(metadata.get("artist") or "Unknown artist"),
        "explanation": _explanation(query, document, match),
        "tags": tags,
        "spotify_href": track_url if verified else search_url,
        "spotify_label": "Open in Spotify" if verified else "Find on Spotify",
        "spotify_verified": verified,
        "distance": distance,
        "match": match,
    }


def _explanation(query: str, document: str, match: str) -> str:
    if match == "exact":
        quote = _best_sentence(query, document)
        return f"The title and artist match your search. Stored description: “{quote}”"
    quote = _best_sentence(query, document)
    return f"Stored description: “{quote}”"


def _best_sentence(query: str, document: str) -> str:
    body = document.split("\n\nTags:", 1)[0].strip() or document.strip()
    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", body) if part.strip()]
    if not sentences:
        return body[:400]
    query_words = _content_words(query)
    if not query_words:
        return sentences[0]

    def score(sentence: str) -> int:
        return len(query_words & _content_words(sentence))

    return max(sentences, key=score)


def _notice(query: str, results: list[dict[str, Any]]) -> str | None:
    if any(card["match"] == "exact" for card in results):
        return None
    semantic = [card for card in results if card["match"] == "semantic"]
    if not semantic:
        return None
    best = semantic[0]
    distance = best["distance"]
    overlap = _content_words(query) & _content_words(best["explanation"])
    if distance is not None and distance >= 0.60:
        return (
            "No close match in the collection. "
            "These are only the nearest stored descriptions."
        )
    if not overlap:
        return (
            "The main words in your search do not appear in the closest stored description. "
            "Read that description before treating the song as a fit."
        )
    return None


def _content_words(text: str) -> set[str]:
    return {
        word
        for word in WORD.findall(text.lower())
        if len(word) >= 4 and word not in STOP_WORDS
    }


def _norm(text: str) -> str:
    return " ".join(text.casefold().split())
