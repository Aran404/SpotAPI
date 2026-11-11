"use strict";

const $ = (selector) => document.querySelector(selector);
const detailCache = new Map();
const detailHistory = [];
let detailRequest = 0;
const state = {
  view: "discover",
  kind: "tracks",
  results: null,
  signedIn: false,
  player: null,
  actions: [],
  polling: false,
  query: "Daft Punk",
  request: 0,
  session: 0,
  selectedAction: null,
};
const icons = (name) => {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  const use = document.createElementNS(svg.namespaceURI, "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
};
const element = (tag, className, text) => {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = String(text);
  return node;
};
const button = (label, className, click) => {
  const node = element("button", className, label);
  node.type = "button";
  node.addEventListener("click", click);
  return node;
};
const minutes = (ms) =>
  `${Math.floor((ms || 0) / 60000)}:${String(Math.floor((ms || 0) / 1000) % 60).padStart(2, "0")}`;

function toast(message) {
  $("#toast").textContent = message;
  $("#toast").classList.add("visible");
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $("#toast").classList.remove("visible"), 5500);
}

async function api(action, values = {}, quiet = false) {
  if (!window.pywebview?.api) {
    if (!quiet)
      toast(
        "Start with python -m examples.studio to connect the Python library.",
      );
    return null;
  }
  const session = state.session;
  try {
    const result = await window.pywebview.api.request(action, values);
    if (session !== state.session) return null;
    if (!result.ok) {
      if (!quiet) toast(result.error);
      return null;
    }
    return result.data ?? { completed: true };
  } catch {
    if (session !== state.session) return null;
    if (!quiet)
      toast("The desktop connection closed. Restart Studio to reconnect.");
    return null;
  }
}

function imageUrl(value) {
  if (!value || typeof value !== "object") return null;
  if (value.image_url) return value.image_url;
  if (value.metadata?.image_url) return value.metadata.image_url;
  for (const key of [
    "cover_art",
    "avatar_image",
    "visuals",
    "coverArt",
    "images",
    "image",
    "album_of_track",
    "album",
  ]) {
    const nested = value[key];
    if (nested) {
      const result = imageUrl(nested);
      if (result) return result;
    }
  }
  if (value.sources?.length) return value.sources[0].url;
  if (value.items?.length) return imageUrl(value.items[0]);
  if (Array.isArray(value)) {
    for (const item of value) {
      const result = imageUrl(item);
      if (result) return result;
    }
  }
  return null;
}

function picture(value, className = "cover") {
  const url = imageUrl(value);
  if (url && /^https:\/\//i.test(url)) {
    const img = element("img", className);
    img.src = url;
    img.alt = "";
    img.loading = "lazy";
    img.referrerPolicy = "no-referrer";
    img.addEventListener(
      "error",
      () => {
        const fallback = element("span", className);
        fallback.append(icons("wave"));
        img.replaceWith(fallback);
      },
      { once: true },
    );
    return img;
  }
  const fallback = element("span", className);
  fallback.append(icons("wave"));
  return fallback;
}

function titleOf(value) {
  if (value != null && typeof value !== "object") return String(value);
  return (
    value?.name ||
    value?.profile?.name ||
    value?.title ||
    value?.field ||
    value?.uri ||
    "Unavailable item"
  );
}
function artistEntries(value) {
  const artists = value?.artists?.items || value?.artists;
  if (Array.isArray(artists) && artists.length)
    return artists;
  return [...(value?.first_artist?.items || []), ...(value?.other_artists?.items || [])];
}
function artistsOf(value) {
  if (value == null || typeof value !== "object") return "";
  if (Array.isArray(value.errors)) return value.errors.join("; ");
  const names = artistEntries(value)
    .map((artist) => artist.profile?.name || artist.name)
    .filter(Boolean);
  if (names.length) return names.join(", ");
  return (
    value?.artist ||
    value?.artist_name ||
    value?.metadata?.artist_name ||
    value?.owner?.data?.name ||
    value?.owner_name ||
    value?.kind ||
    "Spotify"
  );
}
function resourceLink(name, uri) {
  return typeof uri === "string" && uri.startsWith("spotify:")
    ? button(name, "resource-link", () => inspect(uri))
    : document.createTextNode(name);
}
function playerTitle(selector, name, uri) {
  const title = $(selector);
  if (title.dataset.uri === (uri || "") && title.textContent === name) return;
  title.dataset.uri = uri || "";
  title.replaceChildren(resourceLink(name, uri));
}
function artistLine(item, tag = "p") {
  const line = element(tag, "");
  const artists = artistEntries(item).filter((artist) => artist.profile?.name || artist.name);
  artists.forEach((artist, index) => {
    if (index) line.append(", ");
    line.append(resourceLink(artist.profile?.name || artist.name, artist.uri));
  });
  if (!artists.length) line.textContent = artistsOf(item);
  return line;
}
function albumLine(item) {
  const album = item.album_of_track || item.album;
  if (!album?.name) return null;
  const line = element("p", "album-link");
  line.append("Album · ", resourceLink(album.name, album.uri));
  return line;
}
function trackOf(value) {
  return value?.track || value?.item || value;
}

function renderCards(items) {
  const view = $("#view");
  view.className = "cards";
  view.replaceChildren();
  if (!items?.length) {
    view.append(
      element(
        "p",
        "empty-state",
        "Nothing here yet. Try another search or explore a different category.",
      ),
    );
    return;
  }
  for (const item of items) {
    const card = element("div", "music-card");
    card.addEventListener("click", (event) => {
      if (!event.target.closest("button")) inspect(item.uri);
    });
    const title = element("h3", "");
    title.append(resourceLink(titleOf(item), item.uri));
    card.append(
      picture(item, `cover${state.kind === "artists" ? " artist" : ""}`),
      title,
      artistLine(item),
    );
    const album = albumLine(item);
    if (album) card.append(album);
    card.append(element("div", "card-tag", item.uri?.split(":")[1] || "Spotify"));
    const play = button("", "card-play", (event) => {
      event.stopPropagation();
      command("play", { uri: item.uri });
    });
    play.setAttribute("aria-label", `Play ${titleOf(item)}`);
    play.append(icons("play"));
    card.append(play);
    view.append(card);
  }
}

function renderRows(items, target = $("#view")) {
  target.className = "list-view";
  target.replaceChildren();
  if (!items?.length) {
    target.append(
      element(
        "p",
        "empty-state",
        "No items were returned. Spotify may not expose this information for the current session.",
      ),
    );
    return;
  }
  items.forEach((entry, index) => {
    const item = trackOf(entry),
      row = element("div", "track-row"),
      copy = element("div", "row-copy");
    row.append(
      element("span", "rank", String(index + 1).padStart(2, "0")),
      picture(item, "row-art"),
    );
    const title = element("strong", "");
    title.append(resourceLink(titleOf(item), item.uri));
    copy.append(title, artistLine(item, "small"));
    row.append(copy);
    const duration =
      item.duration?.total_milliseconds ??
      item.track_duration?.total_milliseconds ??
      item.duration_ms;
    if (duration)
      row.append(element("span", "row-duration", minutes(duration)));
    if (item.uri) {
      const actions = element("div", "row-actions");
      const play = button("", "icon", () => command("play", { uri: item.uri }));
      play.append(icons("play"));
      play.setAttribute("aria-label", `Play ${titleOf(item)}`);
      const queue = button("", "icon", () =>
        command("queue_add", { uri: item.uri }),
      );
      queue.append(icons("plus"));
      queue.setAttribute("aria-label", `Queue ${titleOf(item)}`);
      actions.append(play);
      if (/^spotify:(track|episode):/.test(item.uri)) actions.append(queue);
      row.append(actions);
    }
    target.append(row);
  });
}

async function search(query) {
  const request = ++state.request;
  state.view = "discover";
  state.query = query;
  setNav("discover");
  $("#hero").hidden = false;
  $("#section-title").textContent =
    query === "Daft Punk"
      ? "A little Daft Punk, and then some."
      : `Explore “${query}”`;
  $("#section-kicker").textContent = "CURRENTLY DIGGING";
  $("#view-status").textContent = "Pulling a few records…";
  $("#section-tools").hidden = false;
  restoreSearchTabs();
  const result = await api("search", { query });
  if (request !== state.request) return;
  $("#view-status").textContent = "";
  if (!result) return;
  state.results = result;
  renderCards(result[state.kind]);
  const art = $("#hero-art");
  art.querySelectorAll("img").forEach((img) => img.remove());
  (result.albums || []).slice(0, 3).forEach((album) => {
    const image = picture(album, "");
    if (image.tagName === "IMG") art.append(image);
  });
}

function setNav(view) {
  document
    .querySelectorAll(".nav")
    .forEach((node) =>
      node.classList.toggle("active", node.dataset.view === view),
    );
}

async function navigate(view, offset = 0) {
  if (view === "discover") {
    search(state.query);
    return;
  }
  const request = ++state.request;
  state.view = view;
  setNav(view);
  $("#hero").hidden = true;
  $("#section-tools").hidden = true;
  $("#view-status").textContent = "";
  const titles = {
    library: "Your record collection",
    liked: "Filed under: keep forever.",
    top: "Your rotation",
    recents: "The trail you left behind",
    notifications: "A little closer to your artists",
    lab: "Make something of your own.",
    events: "Your player, in real time",
    account: "Your account",
  };
  $("#section-title").textContent = titles[view];
  $("#section-kicker").textContent =
    view === "lab" ? "THE WORKBENCH / EVERY KNOB IS CONNECTED" : "YOUR SPACE";
  if (view === "lab") {
    renderLab();
    return;
  }
  if (!state.signedIn) {
    $("#view").className = "list-view";
    $("#view").replaceChildren(
      element(
        "p",
        "empty-state",
        "Connect Spotify to explore your personal collection. Public discovery is already available.",
      ),
    );
    return;
  }
  $("#view-status").textContent = "Reading your Spotify…";
  const data = await api(view === "events" ? "player" : view, {
    offset: String(offset),
  });
  if (request !== state.request) return;
  $("#view-status").textContent = "";
  if (data == null) return;
  if (view === "top") {
    renderRows(data.tracks);
    const tools = $("#section-tools");
    tools.hidden = false;
    tools.replaceChildren();
    for (const [range, label] of [
      ["short_term", "Four weeks"],
      ["medium_term", "Six months"],
      ["long_term", "All time"],
    ]) {
      const control = button(
        label,
        `chip${range === "medium_term" ? " active" : ""}`,
        async () => {
          const next = await api("top", { range });
          if (next && state.view === "top") {
            renderRows(next.tracks);
            tools
              .querySelectorAll("button")
              .forEach((node) =>
                node.classList.toggle("active", node === control),
              );
          }
        },
      );
      tools.append(control);
    }
  } else if (view === "liked" || view === "recents") renderRows(data);
  else if (view === "library") renderRows(data.items);
  else if (view === "events") renderEvents(data.events);
  else if (view === "notifications") renderNotifications(data);
  else renderInfo(data, $("#view"));
  if (view === "library" || view === "liked") {
    const items = view === "library" ? data.items : data;
    const pager = element("div", "pagination");
    if (offset > 0)
      pager.append(
        button("← Previous page", "chip", () =>
          navigate(view, Math.max(0, offset - 50)),
        ),
      );
    pager.append(
      element("span", "subtle", `Page ${Math.floor(offset / 50) + 1}`),
    );
    if (
      typeof data.total === "number"
        ? offset + 50 < data.total
        : items.length === 50
    ) {
      const next = button("Next page →", "chip", () => {
        next.disabled = true;
        navigate(view, offset + 50);
      });
      pager.append(next);
    }
    $("#view").append(pager);
  }
}

function renderInfo(data, target) {
  target.className = "info-grid";
  target.replaceChildren();
  for (const [key, value] of Object.entries(data || {})) {
    if (typeof value === "object" && value !== null) continue;
    const card = element("div", "info-card");
    card.append(
      element("small", "", key.replaceAll("_", " ")),
      element("strong", "", value == null ? "Not supplied" : value),
    );
    target.append(card);
  }
  if (!target.children.length)
    target.append(
      element(
        "p",
        "empty-state",
        "This response has nested data. Expand the typed response below to explore it.",
      ),
    );
}

function renderNotifications(data) {
  const target = $("#view");
  target.className = "list-view";
  target.replaceChildren();
  for (const item of data.items || []) {
    const row = element("div", "track-row"),
      copy = element("div", "row-copy");
    copy.append(
      element("strong", "", item.title),
      element("small", "", new Date(item.created_at).toLocaleDateString()),
    );
    row.append(picture(item, "row-art"), copy);
    target.append(row);
  }
  if (!data.items?.length)
    target.append(
      element(
        "p",
        "empty-state",
        "You're caught up. No notifications were returned.",
      ),
    );
  if (data.forward_cursor)
    target.append(
      button("More updates", "chip", async () => {
        const next = await api("notifications", {
          cursor: data.forward_cursor,
        });
        if (next) renderNotifications(next);
      }),
    );
}

function renderEvents(events = []) {
  const target = $("#view");
  target.className = "list-view";
  target.replaceChildren();
  if (!events.length)
    target.append(
      element(
        "p",
        "empty-state",
        "Listening for real dealer events. Pause or resume Spotify to watch the decorators fire.",
      ),
    );
  for (const event of [...events].reverse().slice(0, 30)) {
    const row = element("div", "event-row");
    row.append(
      element("strong", "", `on_${event.event}`),
      element("small", "", new Date(event.at).toLocaleTimeString()),
      element(
        "p",
        "",
        event.data?.track?.name ||
          event.data?.track?.uri ||
          "Playback state updated",
      ),
    );
    target.append(row);
  }
}

async function inspect(uri, action = "detail") {
  if (!uri) return;
  const request = ++detailRequest;
  const cached = action === "detail" ? detailCache.get(uri) : null;
  const data = cached ?? (await api(action, { uri }));
  if (request !== detailRequest || data == null) return;
  if (action === "radio" && data.uri) {
    await inspect(data.uri, "playlist");
    return;
  }
  const target = document.createDocumentFragment();
  if (action === "detail") {
    detailCache.set(uri, data);
    if (detailCache.size > 20)
      detailCache.delete(detailCache.keys().next().value);
  }
  const item = data.playlist || detailCache.get(uri) || data;
  const hero = element("div", "detail-hero"),
    copy = element("div", "");
  hero.append(picture(item, ""));
  copy.append(
    element("span", "eyebrow", uri.split(":")[1] || "SPOTIFY"),
    element("h2", "", titleOf(item)),
    artistLine(item),
  );
  const album = albumLine(item);
  if (album) copy.append(album);
  hero.append(copy);
  target.append(hero);
  const controls = element("div", "detail-actions");
  controls.append(
    button("Play on Spotify", "primary", () => command("play", { uri })),
  );
  if (/^spotify:(track|episode):/.test(uri))
    controls.append(button("Add to queue", "chip", () => command("queue_add", { uri })));
  if (uri.includes(":track:"))
    controls.append(
      button("Song credits", "chip", () => inspect(uri, "credits")),
      button("Start a radio rabbit hole", "chip", () => inspect(uri, "radio")),
      button("Lyrics · Premium", "chip", () => showLyrics(uri)),
    );
  if (uri.includes(":playlist:"))
    controls.append(
      button("Find similar tracks", "chip", () =>
        inspect(uri, "recommendations"),
      ),
      button("See occurrences", "chip", () => inspect(uri, "playlist")),
    );
  if (uri.includes(":artist:"))
    controls.append(
      button("Related artists", "chip", () => inspect(uri, "related")),
      button("Top tracks", "chip", () => inspect(uri, "artist_top")),
      button("Releases", "chip", () => inspect(uri, "releases")),
    );
  target.append(controls);
  if (Array.isArray(data) || data.items) {
    const list = element("div", "list-view");
    renderRows(Array.isArray(data) ? data : data.items, list);
    target.append(list);
  } else if (data.contributors) {
    target.append(element("h3", "", "THE PEOPLE BEHIND THE SOUND"));
    for (const person of data.contributors) {
      const row = element("div", "track-row");
      const copy = element("div", "row-copy");
      copy.append(
        resourceLink(person.name, person.uri),
        element("small", "", person.role),
      );
      row.append(copy);
      target.append(row);
    }
  } else {
    if (!renderOverview(item, target)) {
      const info = element("div", "info-grid");
      renderInfo(item, info);
      target.append(info);
    }
  }
  addRaw(target, data);
  showDetail(target);
}

function renderOverview(item, target) {
  const bio = item.profile?.biography?.text;
  const tracks = item.tracks_v2?.items || item.discography?.top_tracks?.items;
  const popular = item.discography?.popular_releases_albums?.items;
  const releases = popular?.length
    ? popular
    : item.discography?.albums?.items?.flatMap((group) => group.releases?.items || []);
  if (bio) target.append(element("p", "detail-bio", bio));
  for (const [label, items] of [["Tracks", tracks], ["Releases", releases]]) {
    if (!items?.length) continue;
    const list = element("div", "list-view");
    renderRows(items, list);
    target.append(element("h3", "", label), list);
  }
  return Boolean(bio || tracks?.length || releases?.length);
}

function showDetail(content, lyricsUri = null, lyricsSynced = false) {
  const dialog = $("#detail"),
    body = $("#detail-body");
  if (dialog.open && body.childNodes.length) {
    detailHistory.push({
      nodes: [...body.childNodes],
      scroll: dialog.scrollTop,
      focus: body.contains(document.activeElement) ? document.activeElement : null,
      lyricsUri: state.lyricsUri,
      lyricsSynced: state.lyricsSynced,
    });
    if (detailHistory.length > 12) detailHistory.shift();
  }
  state.lyricsUri = lyricsUri;
  state.lyricsSynced = lyricsSynced;
  body.replaceChildren(content);
  $("#detail-back").hidden = !detailHistory.length;
  if (!dialog.open) dialog.showModal();
  body.focus({ preventScroll: true });
  dialog.scrollTop = 0;
}

function addRaw(target, data) {
  const detail = element("details", ""),
    summary = element("summary", "", "Explore the typed response");
  detail.append(summary, element("pre", "", JSON.stringify(data, null, 2)));
  target.append(detail);
}
async function showLyrics(uri) {
  const request = ++detailRequest;
  const data = await api("lyrics", { uri });
  if (request !== detailRequest || !data) return;
  const target = document.createDocumentFragment();
  target.append(
    element(
      "span",
      "eyebrow",
      `${data.provider || "Lyrics"} · ${data.sync_type}`,
    ),
  );
  const lines = element("div", "lyrics-lines");
  for (const line of data.lines || []) {
    const text = element("p", "", line.words);
    text.dataset.time = line.start_time_ms;
    text.tabIndex = 0;
    text.addEventListener("click", () =>
      command("seek", { position_ms: String(line.start_time_ms) }),
    );
    lines.append(text);
  }
  target.append(lines);
  showDetail(target, uri, data.sync_type === "LINE_SYNCED");
}

function renderLab() {
  const view = $("#view");
  view.className = "lab-layout";
  view.replaceChildren();
  const menu = element("div", "lab-menu"),
    form = element("div", "lab-form");
  let group = "";
  for (const action of state.actions) {
    if (action.group !== group) {
      menu.append(element("h3", "", action.group));
      group = action.group;
    }
    menu.append(button(action.title, "", () => choose(action)));
  }
  function choose(action) {
    state.selectedAction = action;
    menu
      .querySelectorAll("button")
      .forEach((node) =>
        node.classList.toggle("active", node.textContent === action.title),
      );
    form.replaceChildren(
      element("h3", "", action.title),
      element(
        "p",
        "",
        `${action.group} · ${action.authenticated ? "Your authenticated session" : "Works without login"}`,
      ),
    );
    const fields = element("form", "");
    for (const field of action.fields) {
      const label = element("label", "field");
      label.append(element("span", "", field.replaceAll("_", " ")));
      const input = element("input", "");
      input.name = field;
      input.autocomplete = "off";
      input.type = /password|token/.test(field) ? "password" : "text";
      input.placeholder =
        {
          uri: "Spotify URL, URI, or ID",
          uris: "Spotify URIs, separated by spaces",
          playlist: "Playlist URL, URI, or ID",
          user: "Spotify username",
          users: "Usernames, separated by spaces",
          uids: "Occurrence UIDs, separated by spaces",
          birthdate: "YYYY-MM-DD",
          token: "Fresh CAPTCHA token from your own provider",
        }[field] || field;
      label.append(input);
      fields.append(label);
    }
    if (action.changes)
      fields.append(
        element(
          "p",
          "change-note",
          "This changes your account or playback. You'll review it before sending.",
        ),
      );
    const run = element("button", "primary", "Try it with SpotAPI");
    run.type = "submit";
    fields.append(run);
    fields.addEventListener("submit", async (event) => {
      event.preventDefault();
      const values = Object.fromEntries(new FormData(fields));
      if (action.changes && !(await confirmChange(action.title))) {
        fields.querySelectorAll('input[type="password"]').forEach((input) => {
          input.value = "";
        });
        return;
      }
      values.confirmed = "true";
      run.disabled = true;
      run.textContent = "Working…";
      const result = await api(action.id, values);
      run.disabled = false;
      run.textContent = "Try it with SpotAPI";
      if (result != null) {
        const target = document.createDocumentFragment();
        target.append(element("h2", "", action.title));
        if (Array.isArray(result)) {
          const list = element("div", "");
          renderRows(result, list);
          target.append(list);
        } else if (typeof result === "object") {
          const info = element("div", "");
          renderInfo(result, info);
          target.append(info);
        } else target.append(element("p", "", result));
        addRaw(target, result);
        showDetail(target);
      }
      if (action.id === "logout_everywhere" && result != null) {
        await bootstrap();
        updatePlayer({ state: null, devices: [], events: [], queue: [] });
      }
      fields.querySelectorAll('input[type="password"]').forEach((input) => {
        input.value = "";
      });
    });
    form.append(fields);
  }
  view.append(menu, form);
  if (state.actions.length) choose(state.selectedAction || state.actions[0]);
}

function confirmChange(title) {
  $("#confirm-title").textContent = title + "?";
  $("#confirm").returnValue = "cancel";
  $("#confirm").showModal();
  return new Promise((resolve) =>
    $("#confirm").addEventListener(
      "close",
      () => resolve($("#confirm").returnValue === "apply"),
      { once: true },
    ),
  );
}

async function command(action, values = {}) {
  if (!state.signedIn) {
    toast("Connect Spotify, then open a song on an existing device.");
    return;
  }
  const result = await api(action, { ...values, confirmed: "true" });
  if (result != null) {
    if (action === "queue_add") toast("Added to your Spotify queue");
    await pollPlayer();
  }
}

async function pollPlayer() {
  if (state.polling || !state.signedIn) return;
  state.polling = true;
  const session = state.session;
  try {
    const data = await api("player", {}, true);
    if (session !== state.session) return;
    if (data) updatePlayer(data);
    else
      $("#now-artist").textContent =
        "Player unavailable · refresh to reconnect";
  } finally {
    state.polling = false;
  }
}

function updatePlayer(data) {
  state.player = data;
  const track = data.state?.track,
    name = track?.name || track?.metadata?.title || "No active track",
    artist = artistsOf(track);
  playerTitle("#now-name", name, track?.uri);
  $("#now-artist").textContent = track
    ? artist
    : "Open a song on an existing Spotify device";
  playerTitle("#bar-title", name, track?.uri);
  $("#bar-artist").textContent = track ? artist : "Choose a device in Spotify";
  const coverKey = (track?.uri || "") + (imageUrl(track) || "");
  if (coverKey !== state.coverKey) {
    $("#now-art").replaceChildren(picture(track, ""));
    $("#mini-cover").replaceChildren(picture(track, ""));
    state.coverKey = coverKey;
  }
  $("#play-icon use").setAttribute(
    "href",
    data.state?.is_playing ? "#i-pause" : "#i-play",
  );
  $("#shuffle").classList.toggle("active", !!data.state?.shuffle);
  $("#repeat").classList.toggle(
    "active",
    !!(data.state?.repeat_context || data.state?.repeat_track),
  );
  const restrictions = data.state?.restrictions || {};
  $("#shuffle").disabled =
    !!restrictions.disallow_toggling_shuffle_reasons?.length;
  $("#shuffle").title = $("#shuffle").disabled
    ? "Spotify disables shuffle for this context"
    : "Toggle shuffle";
  $("#repeat").disabled = !!(
    restrictions.disallow_toggling_repeat_context_reasons?.length ||
    restrictions.disallow_toggling_repeat_track_reasons?.length
  );
  $("#repeat").title = $("#repeat").disabled
    ? "Spotify disables repeat for this context"
    : "Cycle repeat";
  const position = data.state?.position || 0,
    duration = data.state?.duration_ms || 1;
  $("#elapsed").textContent = minutes(position);
  $("#duration").textContent = minutes(duration);
  if (document.activeElement !== $("#seek")) {
    $("#seek").max = duration;
    $("#seek").value = position;
  }
  const devices = $("#devices"),
    selected = devices.value;
  devices.replaceChildren();
  for (const device of data.devices || []) {
    const option = element("option", "", device.name);
    option.value = device.id;
    option.selected = device.id === (data.state?.active_device_id || selected);
    devices.append(option);
  }
  if (!devices.children.length)
    devices.append(element("option", "", "No active device"));
  const activeDevice = (data.devices || []).find(
    (device) => device.id === data.state?.active_device_id,
  );
  if (
    typeof activeDevice?.volume === "number" &&
    document.activeElement !== $("#volume")
  ) {
    $("#volume").value = Math.round((activeDevice.volume * 100) / 65535);
  }
  const next = data.queue || data.state?.next_tracks || [];
  $("#queue-count").textContent = data.state?.next_tracks?.length
    ? `${data.state.next_tracks.length} in view`
    : "—";
  const queue = $("#queue");
  queue.replaceChildren();
  for (const item of next.slice(0, 12)) {
    const row = element("div", "queue-row"),
      copy = element("div", "");
    copy.append(
      element("strong", "", item.name || item.metadata?.title || item.uri),
      element("small", "", artistsOf(item)),
    );
    row.append(picture(item, "queue-thumb"), copy);
    if (item.provider === "queue" && item.uid)
      row.append(
        button("×", "icon", () => command("queue_remove", { uid: item.uid })),
      );
    queue.append(row);
  }
  if (!next.length)
    queue.append(
      element(
        "p",
        "empty-copy",
        "Nothing queued. Find a track and add it with +.",
      ),
    );
  if (state.view === "events") renderEvents(data.events);
  highlightLyrics();
}

function highlightLyrics() {
  if (
    !state.lyricsSynced ||
    state.lyricsUri !== state.player?.state?.track?.uri
  )
    return;
  const lines = [...document.querySelectorAll(".lyrics-lines p")];
  const position = state.player.state.position || 0;
  const active = lines.reduce(
    (latest, line) =>
      Number(line.dataset.time) <= position
        ? Number(line.dataset.time)
        : latest,
    -1,
  );
  lines.forEach((line) =>
    line.classList.toggle("current", Number(line.dataset.time) === active),
  );
}

function resetSession() {
  state.session++;
  state.request++;
  detailCache.clear();
  clearDetailNavigation();
  state.results = null;
  $("#detail").close();
  $("#detail-body").replaceChildren();
  $("#view").replaceChildren();
  updatePlayer({ state: null, devices: [], events: [], queue: [] });
}

async function bootstrap(reset = false) {
  if (reset) resetSession();
  const data = await api("bootstrap");
  if (!data) return false;
  if (!reset && (state.accountName !== data.name || state.signedIn !== data.signed_in))
    resetSession();
  state.accountName = data.name;
  state.signedIn = data.signed_in;
  state.actions = data.actions;
  $("#session-label").textContent = state.signedIn
    ? "Spotify connected"
    : "Public session";
  $("#login").textContent = state.signedIn
    ? "Switch Spotify account"
    : "Connect Spotify";
  $("#account-button").textContent = (data.name || "S")
    .slice(0, 1)
    .toUpperCase();
  if (state.view === "lab") renderLab();
  return true;
}

window.studio = {
  signedIn: async () => {
    if (!(await bootstrap(true))) return;
    toast("Connected. Your music is ready to explore.");
    pollPlayer();
    if (state.view !== "discover") navigate(state.view);
    else search(state.query);
  },
  loginFailed: () =>
    toast(
      "Spotify couldn't validate this session. Use Connect Spotify to sign in again.",
    ),
};

document
  .querySelectorAll("[data-view]")
  .forEach((node) =>
    node.addEventListener("click", () => navigate(node.dataset.view)),
  );
document
  .querySelectorAll("[data-command]")
  .forEach((node) =>
    node.addEventListener("click", () => command(node.dataset.command)),
  );
function restoreSearchTabs() {
  const tools = $("#section-tools");
  tools.replaceChildren();
  for (const kind of [
    "tracks",
    "artists",
    "albums",
    "playlists",
    "podcasts",
    "episodes",
    "audiobooks",
    "users",
    "authors",
    "genres",
  ]) {
    const tab = button(
      kind[0].toUpperCase() + kind.slice(1),
      "chip" + (state.kind === kind ? " active" : ""),
      () => {
        state.kind = kind;
        restoreSearchTabs();
        if (state.results) renderCards(state.results[kind]);
      },
    );
    tools.append(tab);
  }
}
$("#search-form").addEventListener("submit", (event) => {
  event.preventDefault();
  const value = $("#search").value.trim();
  if (!value) return;
  if (/^(spotify:|https:\/\/open.spotify.com\/)/.test(value)) inspect(value);
  else search(value);
});
$("#hero-explore").addEventListener("click", () => {
  $("#search").focus();
  $("#search").select();
});
$("#login").addEventListener("click", async () => {
  const result = await window.pywebview?.api.login();
  if (result && !result.ok) toast(result.error);
});
$("#account-button").addEventListener("click", () => navigate("account"));
$("#refresh-player").addEventListener("click", async () => {
  const result = await api("refresh_player");
  if (result) updatePlayer(result);
});
$("#lyrics").addEventListener("click", () =>
  state.player?.state?.track?.uri
    ? showLyrics(state.player.state.track.uri)
    : toast("Open a track in Spotify first."),
);
$("#shuffle").addEventListener("click", () =>
  command("shuffle", { enabled: String(!state.player?.state?.shuffle) }),
);
$("#repeat").addEventListener("click", () => {
  const current = state.player?.state;
  command("repeat", {
    mode: current?.repeat_track
      ? "off"
      : current?.repeat_context
        ? "track"
        : "context",
  });
});
$("#seek").addEventListener("change", () =>
  command("seek", { position_ms: $("#seek").value }),
);
$("#volume").addEventListener("change", () =>
  command("volume", { percent: $("#volume").value }),
);
$("#devices").addEventListener("change", () =>
  command("transfer", { device: $("#devices").value }),
);
$("#like-current").addEventListener("click", () => {
  const uri = state.player?.state?.track?.uri;
  if (uri) command("saved_add", { uris: uri });
});
function clearDetailNavigation() {
  detailRequest++;
  detailHistory.length = 0;
  $("#detail-back").hidden = true;
  state.lyricsUri = null;
  state.lyricsSynced = false;
}
$(".close-dialog").addEventListener("click", () => {
  clearDetailNavigation();
  $("#detail").close();
});
$("#detail").addEventListener("cancel", clearDetailNavigation);
$("#detail").addEventListener("close", () => {
  if (!$("#detail").open) clearDetailNavigation();
});
$("#detail-back").addEventListener("click", () => {
  const previous = detailHistory.pop();
  if (!previous) return;
  detailRequest++;
  const body = $("#detail-body");
  body.replaceChildren(...previous.nodes);
  state.lyricsUri = previous.lyricsUri;
  state.lyricsSynced = previous.lyricsSynced;
  $("#detail-back").hidden = !detailHistory.length;
  (previous.focus || body).focus({ preventScroll: true });
  $("#detail").scrollTop = previous.scroll;
});
document.addEventListener("keydown", (event) => {
  if (
    event.key === "/" &&
    !["INPUT", "TEXTAREA"].includes(document.activeElement.tagName)
  ) {
    event.preventDefault();
    $("#search").focus();
  }
});
window.addEventListener("pywebviewready", async () => {
  await bootstrap();
  await search("Daft Punk");
  if (state.signedIn) pollPlayer();
});
setInterval(pollPlayer, 4000);
