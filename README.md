# FindMusic

A small music discovery app for a vector-database project. Search and adding a song go through a FastAPI backend and a single web page. The songs live in a local Chroma collection.

Personal assignment reflections are intentionally not written in this file.

## Source data

The corpus comes from the Song Describer Dataset, CC BY-SA 4.0:

Manco, I., Weck, B., Bogdanov, D., Tovstogan, P., & Won, M. (2023). *Song Describer Dataset* (Version 1.0.0) [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.10072001

The loader checks the Zenodo MD5 checksums, joins each caption to its Jamendo title and artist, and stores one record per track. The embedded text is the human caption plus the dataset’s genre, instrument, and mood tags. Titles and artist names are stored as metadata and are not part of the embedded text.

The dataset does not include Spotify track IDs. Each record stores an empty `spotify_track_url` and a `spotify_search_url` of the form `https://open.spotify.com/search/{title artist}`.

Raw files and the Chroma directory are written under `data/` and are not committed.

## Setup

Developed with Python 3.13.3 and ChromaDB 1.5.9. Embeddings use Chroma’s built-in ONNX `all-MiniLM-L6-v2` model (`ONNXMiniLM_L6_V2`), with cosine distance. The model is downloaded to the local Chroma cache on first use. That model embeds at most 256 tokens; longer stored captions are kept in full, and the vector uses the truncated portion.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn findmusic.web:app --app-dir .
```

Open http://127.0.0.1:8000. The server loads all 706 tracks into `data/chroma` on first use if they are not already there. Added songs are written to that same collection.

`scripts/load_corpus.py` can load the corpus ahead of time. It upserts in batches of 100 and keeps the same ids when run again. `scripts/evaluate_queries.py` and `scripts/query_sample.py` only read the collection.

The hosted app is at https://findmusic-one.vercel.app. A function can write only to temporary storage, so songs added there last until that instance stops. A local run keeps them in `data/chroma`. The live deploy also includes the local collection and the ONNX model from this machine. Those files stay out of Git.
