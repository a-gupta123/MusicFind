# FindMusic

A small music discovery app for a vector-database project. This repository currently contains stage 2: a persistent local Chroma collection loaded with a 40-track sample. Search, song addition, and the web interface are not built yet.

Personal assignment reflections are intentionally not written in this file.

## Source data

The sample comes from the Song Describer Dataset, CC BY-SA 4.0:

Manco, I., Weck, B., Bogdanov, D., Tovstogan, P., & Won, M. (2023). *Song Describer Dataset* (Version 1.0.0) [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.10072001

The loader checks the Zenodo MD5 checksums, joins each caption to its Jamendo title and artist, and stores one record per track. The embedded text is the human caption plus the dataset’s genre, instrument, and mood tags. Titles and artist names are stored as metadata and are not part of the embedded text.

The dataset does not include Spotify track IDs. Each record stores an empty `spotify_track_url` and a `spotify_search_url` of the form `https://open.spotify.com/search/{title artist}`.

Raw files and the Chroma directory are written under `data/` and are not committed.

## Setup

Developed with Python 3.13.3 and ChromaDB 1.5.9. Embeddings use Chroma’s built-in ONNX `all-MiniLM-L6-v2` model (`ONNXMiniLM_L6_V2`), with cosine distance. The model is downloaded to the local Chroma cache on first use. That model embeds at most 256 tokens; longer stored captions are kept in full, and the vector uses the truncated portion.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python scripts/load_sample.py
.venv/bin/python scripts/query_sample.py
```

`load_sample.py` can be run again. It upserts the same Jamendo ids, so the collection count stays at 40. `query_sample.py` only reads the collection.
