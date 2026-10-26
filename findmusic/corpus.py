"""Load Song Describer tracks and build the text that gets embedded."""

from __future__ import annotations

import csv
import hashlib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlretrieve

# Published checksums from Zenodo record 10.5281/zenodo.10072001.
RAW_FILES = {
    "song_describer.csv": {
        "url": "https://zenodo.org/records/10072001/files/song_describer.csv?download=1",
        "md5": "e90e9459c22bfbe69f5462dc1434d573",
    },
    "audio_metadata.tsv": {
        "url": "https://zenodo.org/records/10072001/files/audio_metadata.tsv?download=1",
        "md5": "fa5d126659b08680719d189387d61e39",
    },
    "song_describer_mtg_jamendo.tsv": {
        "url": "https://zenodo.org/records/10072001/files/song_describer_14_04_23.mtg-jamendo.tsv?download=1",
        "md5": "3532f2df8b4c21a7ea85d9121eae244a",
    },
}

# Tracks opened during stage 1. They are always part of the sample so a
# later query can be compared with text we have already read.
INSPECTED_TRACK_IDS = (1116406, 103892, 1007274, 1009674, 1051197)
SAMPLE_SIZE = 40

SOURCE_NAME = "Song Describer Dataset"
SOURCE_DOI = "10.5281/zenodo.10072001"
SOURCE_LICENSE = "CC BY-SA 4.0"


@dataclass(frozen=True)
class Song:
    track_id: int
    title: str
    artist: str
    album: str
    source_url: str
    tags: tuple[str, ...]
    captions: tuple[str, ...]
    has_validated_caption: bool

    @property
    def record_id(self) -> str:
        return f"jamendo-{self.track_id}"

    @property
    def document(self) -> str:
        """Descriptive text only. Title and artist stay in metadata."""
        captions = "\n\n".join(self.captions)
        if self.tags:
            tag_line = ", ".join(_tag_label(tag) for tag in self.tags)
            return f"{captions}\n\nTags: {tag_line}"
        return captions

    @property
    def spotify_search_url(self) -> str:
        query = quote(f"{self.title} {self.artist}", safe="")
        return f"https://open.spotify.com/search/{query}"

    def metadata(self) -> dict[str, str | int | bool]:
        return {
            "track_id": str(self.track_id),
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "tags": ", ".join(_tag_label(tag) for tag in self.tags),
            "source": SOURCE_NAME,
            "source_url": self.source_url,
            "spotify_track_url": "",
            "spotify_search_url": self.spotify_search_url,
            "caption_count": len(self.captions),
            "has_validated_caption": self.has_validated_caption,
        }


def raw_dir(root: Path) -> Path:
    return root / "data" / "raw"


def ensure_raw_files(root: Path) -> Path:
    directory = raw_dir(root)
    directory.mkdir(parents=True, exist_ok=True)
    for name, spec in RAW_FILES.items():
        path = directory / name
        if path.exists() and _md5(path) == spec["md5"]:
            continue
        urlretrieve(spec["url"], path)
        digest = _md5(path)
        if digest != spec["md5"]:
            path.unlink(missing_ok=True)
            raise RuntimeError(
                f"{name} md5 was {digest}, expected {spec['md5']} from Zenodo."
            )
    return directory


def load_songs(root: Path) -> list[Song]:
    directory = ensure_raw_files(root)
    metadata = _read_metadata(directory / "audio_metadata.tsv")
    tags = _read_tags(directory / "song_describer_mtg_jamendo.tsv")
    captions: dict[int, list[str]] = {}
    validated: dict[int, bool] = {}

    with (directory / "song_describer.csv").open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            track_id = _track_id(row["track_id"])
            text = (row.get("caption") or "").strip()
            if text:
                captions.setdefault(track_id, []).append(text)
            if row.get("is_valid_subset") == "True":
                validated[track_id] = True

    missing = sorted(set(captions) - set(metadata))
    if missing:
        raise RuntimeError(f"Captions without metadata: {missing[:5]}")

    songs = []
    for track_id, texts in captions.items():
        info = metadata[track_id]
        songs.append(
            Song(
                track_id=track_id,
                title=info["title"],
                artist=info["artist"],
                album=info["album"],
                source_url=info["url"],
                tags=tuple(tags.get(track_id, ())),
                captions=tuple(texts),
                has_validated_caption=validated.get(track_id, False),
            )
        )
    songs.sort(key=lambda song: song.track_id)
    return songs


def select_sample(songs: list[Song], size: int = SAMPLE_SIZE) -> list[Song]:
    """Five inspected tracks, then the lowest remaining track ids, up to `size`."""
    by_id = {song.track_id: song for song in songs}
    missing = [track_id for track_id in INSPECTED_TRACK_IDS if track_id not in by_id]
    if missing:
        raise RuntimeError(f"Inspected tracks missing from the corpus: {missing}")
    chosen = [by_id[track_id] for track_id in INSPECTED_TRACK_IDS]
    chosen_ids = set(INSPECTED_TRACK_IDS)
    for song in songs:
        if len(chosen) >= size:
            break
        if song.track_id in chosen_ids:
            continue
        chosen.append(song)
    return chosen


def _tag_label(tag: str) -> str:
    if "---" not in tag:
        return tag
    kind, name = tag.split("---", 1)
    return f"{kind}: {name}"


def _track_id(value: str) -> int:
    text = value.strip()
    if text.startswith("track_"):
        text = text.split("_", 1)[1]
    return int(text)


def _read_metadata(path: Path) -> dict[int, dict[str, str]]:
    records = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            track_id = _track_id(row[0])
            records[track_id] = {
                "title": row[3],
                "artist": row[4],
                "album": row[5],
                "url": row[7],
            }
    return records


def _read_tags(path: Path) -> dict[int, tuple[str, ...]]:
    records = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.reader(handle, delimiter="\t"):
            track_id = _track_id(row[0])
            records[track_id] = tuple(cell for cell in row[5:] if cell)
    return records


def _md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
