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
RESULT_LIMIT = 12
ARTIST_CAP = 20
# Only warn when the nearest song is far from the query. A name match is a real hit.
NO_CLOSE_DISTANCE = 0.70
GENERIC_NAME_WORDS = STOP_WORDS | {
    "music",
    "production",
    "records",
    "record",
    "band",
    "project",
    "sound",
    "sounds",
    "blues",
    "rock",
    "jazz",
    "soul",
    "folk",
    "piano",
    "guitar",
    "vocal",
    "vocals",
    "singing",
    "singer",
    "fresh",
    "love",
    "king",
    "play",
    "girl",
    "shop",
    "body",
    "beat",
    "feat",
    "featuring",
    "cool",
    "high",
    "real",
    "soft",
    "slow",
    "hard",
    "deep",
    "warm",
    "dark",
    "male",
    "female",
}


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
    semantic = _cards_from_query(found, text, "semantic")
    stored = collection.get(include=["metadatas", "documents"], limit=total)
    artist_matches = _artist_matches(collection, text, stored)
    results = _merge_named(text, stored, artist_matches, semantic)
    results = _promote_exact(text, results)
    notice = _notice(text, results)
    return {
        "query": text,
        "count": len(results),
        "notice": notice,
        "results": results,
    }


def _cards_from_query(found: dict[str, Any], query: str, match: str) -> list[dict[str, Any]]:
    cards = []
    ids = found.get("ids") or [[]]
    distances = found.get("distances") or [[]]
    metadatas = found.get("metadatas") or [[]]
    documents = found.get("documents") or [[]]
    if not ids or not ids[0]:
        return cards
    for record_id, distance, metadata, document in zip(
        ids[0],
        distances[0],
        metadatas[0],
        documents[0],
    ):
        if metadata is None:
            continue
        cards.append(
            _card(
                record_id=record_id,
                metadata=metadata,
                document=document or "",
                distance=float(distance),
                match=match,
                query=query,
            )
        )
    return cards


def _artist_matches(
    collection: Collection,
    query: str,
    stored: dict[str, Any],
) -> list[dict[str, Any]]:
    """Songs whose artist name, or a distinctive part of it, appears in the query."""
    groups = _group_by_artist(stored)
    query_tokens = {
        word
        for word in WORD.findall(query.casefold())
        if len(word) >= 4 and word not in GENERIC_NAME_WORDS
    }
    query_norm = _norm(query)
    matched = []
    for artist, group in groups.items():
        artist_norm = _norm(artist)
        phrase = bool(artist_norm) and f" {artist_norm} " in f" {query_norm} "
        tokens = group["tokens"] & query_tokens
        if phrase or tokens:
            used = set(WORD.findall(artist.casefold())) if phrase else tokens
            matched.append((artist, used))
    if not matched:
        return []

    ranked = []
    for artist, used_tokens in matched:
        remainder = _remainder(query, used_tokens)
        ranked.extend(_songs_for_artist(collection, query, artist, remainder, groups[artist]["count"]))
    ranked.sort(key=lambda card: (card["distance"] is None, card["distance"] if card["distance"] is not None else 0))
    deduped = []
    seen = set()
    for card in ranked:
        if card["id"] in seen:
            continue
        seen.add(card["id"])
        deduped.append(card)
    return deduped[:ARTIST_CAP]


def _group_by_artist(stored: dict[str, Any]) -> dict[str, dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for metadata in stored.get("metadatas") or []:
        if metadata is None:
            continue
        artist = str(metadata.get("artist") or "")
        if not artist.strip():
            continue
        group = groups.setdefault(artist, {"tokens": set(), "count": 0})
        group["count"] += 1
        group["tokens"].update(
            word
            for word in WORD.findall(artist.casefold())
            if len(word) >= 4 and word not in GENERIC_NAME_WORDS
        )
    return groups


def _remainder(query: str, artist_tokens: set[str]) -> str:
    words = [word for word in WORD.findall(query) if word.casefold() not in artist_tokens]
    return " ".join(words)


def _songs_for_artist(
    collection: Collection,
    query: str,
    artist: str,
    remainder: str,
    count: int,
) -> list[dict[str, Any]]:
    probe = remainder if len(remainder) >= 3 else query
    found = collection.query(
        query_texts=[probe],
        n_results=min(ARTIST_CAP, count),
        where={"artist": artist},
    )
    return _cards_from_query(found, query, "artist")


def _merge_named(
    query: str,
    stored: dict[str, Any],
    artist_matches: list[dict[str, Any]],
    semantic: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    exact = _exact_cards(query, stored, {card["id"] for card in artist_matches})
    if artist_matches:
        if len(artist_matches) >= 5:
            return exact + artist_matches
        seen = {card["id"] for card in exact + artist_matches}
        filler = [card for card in semantic if card["id"] not in seen]
        return (exact + artist_matches + filler)[:RESULT_LIMIT]
    return exact + semantic


def _exact_cards(
    query: str,
    stored: dict[str, Any],
    skip: set[str],
) -> list[dict[str, Any]]:
    needle = _norm(query)
    if len(needle) < 2:
        return []
    exact = []
    ids = stored.get("ids") or []
    metadatas = stored.get("metadatas") or []
    documents = stored.get("documents") or []
    for record_id, metadata, document in zip(ids, metadatas, documents):
        if metadata is None or record_id in skip:
            continue
        names = {
            _norm(str(metadata.get("title", ""))),
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
    return exact


def _promote_exact(query: str, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    needle = _norm(query)
    promoted = []
    rest = []
    for card in results:
        names = {
            _norm(card["title"]),
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
    quote = _best_sentence(query, document)
    if match == "exact":
        return f"The title and artist match your search. Stored description: “{quote}”"
    if match == "artist":
        return f"The artist name matches your search. Stored description: “{quote}”"
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
    if any(card["match"] in {"exact", "artist"} for card in results):
        return None
    semantic = [card for card in results if card["match"] == "semantic" and card["distance"] is not None]
    if not semantic:
        return None
    best = min(semantic, key=lambda card: card["distance"])
    distance = best["distance"]
    overlap = _content_words(query) & _content_words(best["explanation"])
    if distance is not None and distance >= NO_CLOSE_DISTANCE:
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
