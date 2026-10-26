# FindMusic

I built FindMusic so that I could search for songs by describing a mood, the instruments, or the situation I wanted to hear, instead of having to already know the title. I chose this for my vector database project because the same request can be phrased in many ways, and a keyword search would miss a caption that uses different words for the same idea.

## What I store

I store one item per track from the Song Describer Dataset, which is licensed CC BY-SA 4.0. The citation is Manco, I., Weck, B., Bogdanov, D., Tovstogan, P., and Won, M. (2023). *Song Describer Dataset* (Version 1.0.0) [Dataset]. Zenodo. https://doi.org/10.5281/zenodo.10072001. One item is one track. I did not break the captions into smaller pieces, because each caption is already about one song, and a check of all 706 documents found that none of them were cut off by the model's 256-token limit. The text that gets embedded is the human caption plus a line of genre, instrument, and mood tags. The title, the artist, the source, and the Spotify link are metadata, because I did not want a search for a mood to depend on the song name. I loaded 706 tracks. The raw files and the Chroma folder are under `data/`, and they are not committed. On a first run the app downloads those Song Describer files from Zenodo, checks their MD5 checksums, and loads them. `scripts/load_corpus.py` can do that load ahead of time. It upserts in batches of 100 and keeps the same record ids when it is run again.

## How a user adds a song, and how a user searches

A user searches by typing a description into the search bar. The app returns up to 12 songs, ranked by how close the stored description is to the query, and each result shows the title, the artist, a quoted caption, the tags, and a Spotify link. If the query names an artist that is actually in the collection, that artist's songs are listed first, up to 20, and a description in the same query ranks those songs. If nothing stored is close, the page says so instead of treating the nearest songs as a good match. A user adds a song with the Add a song form while the app is running. The form takes a title, an artist, a description of at least 20 characters, optional tags, and an optional Spotify track URL. The song is written into the same collection, so a search can find it immediately, and on a local run it is still there after the program is closed and opened again.

## Two queries a keyword search would miss

I ran these on 26 October 2026 against the 706-song collection. I checked the top caption for the important words in each query, and none of those words appear.

`falling asleep in a chair`

The top result was Satie, E.: Gymnopédies - I. Lent et douloureux by OnClassical, id jamendo-1169730, distance 0.6786067485809326. The stored text says "Suitable for relaxing and sleeping." The words falling, asleep, and chair do not appear. A keyword search would miss this song, because the caption says sleeping rather than asleep, and it never mentions a chair.

`a tune to put a grown person to bed`

The top result was Sweet Dreams by Esther Garcia, id jamendo-1151409, distance 0.5200722813606262. The stored text calls it "A lullaby turned dark in its melody." The words tune, grown, person, and bed do not appear. A keyword search for those words would miss the song, because the caption expresses the same idea with lullaby.

## How I used AI

I used Grok 4.7 in Cursor to implement the app one stage at a time, and to debug the data loading, the search, and the checks recorded in [prompt_log.md](prompt_log.md). I used that tool because I was building the project in Cursor, and I wanted to check each stage before I moved on, rather than generate the whole app from the assignment in one prompt. The app does not call a language model. The embeddings come from Chroma's local model, and the explanation under each song is a quote from the stored caption.

## How to run it

I used Python 3.13.3, FastAPI 0.162.0, and ChromaDB 1.5.9. The vector database is a Chroma `PersistentClient` at `data/chroma`, with cosine distance. The embedding model is Chroma's ONNX `all-MiniLM-L6-v2` model. That model is downloaded once into the local Chroma cache the first time it is needed, unless a copy is already present.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/uvicorn findmusic.web:app --app-dir .
```

Open http://127.0.0.1:8000. `scripts/evaluate_queries.py` and `scripts/query_sample.py` only read the collection.

The hosted page is https://findmusic-one.vercel.app. Songs added there are stored in temporary instance storage and disappear when that instance stops, so the persistence check should be done on a local run.

## Spotify links

The corpus has Jamendo URLs and no Spotify track ids. Those songs use a Spotify search link for the title and artist, labeled "Find on Spotify." A song added in the app can include a track URL. Only `https://open.spotify.com/track/{22-character id}` is stored, including an `intl-xx` link, which is saved in the canonical track form and labeled "Open in Spotify." Any other link is rejected.
