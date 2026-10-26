const searchForm = document.querySelector("#search-form");
const queryInput = document.querySelector("#query");
const searchButton = document.querySelector("#search-button");
const status = document.querySelector("#status");
const notice = document.querySelector("#notice");
const results = document.querySelector("#results");
const dialog = document.querySelector("#add-dialog");
const addForm = document.querySelector("#add-form");
const addError = document.querySelector("#add-error");
const addButton = document.querySelector("#add-button");
const persistence = document.querySelector("#persistence");

document.querySelector("#open-add").addEventListener("click", () => {
  addError.hidden = true;
  dialog.showModal();
});

document.querySelector("#close-add").addEventListener("click", () => dialog.close());

document.querySelectorAll(".examples button").forEach((button) => {
  button.addEventListener("click", () => {
    queryInput.value = button.textContent;
    searchForm.requestSubmit();
  });
});

searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  search(queryInput.value);
});

addForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  addError.hidden = true;
  addButton.disabled = true;
  const payload = Object.fromEntries(new FormData(addForm));
  try {
    const response = await fetch("/api/songs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const body = await readJson(response);
    if (!response.ok) {
      throw new Error(body.detail || "Could not save the song.");
    }
    dialog.close();
    addForm.reset();
    queryInput.value = `${body.title} ${body.artist}`;
    await search(queryInput.value);
  } catch (error) {
    addError.hidden = false;
    addError.textContent = error.message;
  } finally {
    addButton.disabled = false;
  }
});

async function search(query) {
  const text = query.trim();
  if (!text) return;
  searchButton.disabled = true;
  results.replaceChildren();
  notice.hidden = true;
  status.textContent = "Searching…";
  const slowNote = window.setTimeout(() => {
    status.textContent = "Loading the song collection. The first search can take about a minute.";
  }, 1500);
  try {
    const response = await fetch(`/api/search?q=${encodeURIComponent(text)}`);
    const body = await readJson(response);
    if (!response.ok) {
      throw new Error(body.detail || "Search failed.");
    }
    status.textContent = body.results.length
      ? `${body.results.length} songs`
      : "No songs found.";
    if (body.notice) {
      notice.hidden = false;
      notice.textContent = body.notice;
    }
    body.results.forEach((song) => results.append(renderSong(song)));
  } catch (error) {
    status.textContent = "";
    notice.hidden = false;
    notice.textContent = error.message;
  } finally {
    window.clearTimeout(slowNote);
    searchButton.disabled = false;
  }
}

async function readJson(response) {
  const raw = await response.text();
  try {
    return JSON.parse(raw);
  } catch {
    return { detail: "The server returned an unexpected response." };
  }
}

function renderSong(song) {
  const item = document.createElement("li");
  item.className = "result";
  const title = document.createElement("h2");
  title.textContent = song.title;
  const artist = document.createElement("p");
  artist.className = "artist";
  artist.textContent = song.artist;
  const explanation = document.createElement("p");
  explanation.className = "explanation";
  explanation.textContent = song.explanation;
  item.append(title, artist, explanation);
  if (song.tags && song.tags.length) {
    const tags = document.createElement("ul");
    tags.className = "tags";
    song.tags.forEach((tag) => {
      const chip = document.createElement("li");
      chip.textContent = tag;
      tags.append(chip);
    });
    item.append(tags);
  }
  if (song.spotify_href) {
    const link = document.createElement("a");
    link.href = song.spotify_href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.textContent = song.spotify_label;
    item.append(link);
  }
  return item;
}

fetch("/api/health")
  .then((response) => response.json())
  .then((body) => {
    if (body.persistent === false) persistence.hidden = false;
  })
  .catch(() => {});
