# Discovery, previews and captions

These APIs are part of the current development checkout. Check the installed
release before using them in an existing application; use `pip install -e .`
from the repository root to exercise `main`.

## Charts, recommendations and concerts

```python
from spotapi import Catalogue

async def explore(track_url, artist_url):
    async with Catalogue() as spotify:
        albums = await spotify.get_similar_albums(track_url, limit=10)
        concerts = await spotify.get_artist_events(artist_url)
        charts = spotify.list_charts()
        chart = await spotify.get_chart(charts[0].key)
        async for page in spotify.get_playlist_items(chart.uri):
            print(page)
```

Charts are shortcuts to editorial playlists, not a separate historical rankings
service. Inventory can be retired. Concerts and recommendations may be empty
and can vary by region. Missing response collections raise errors rather than
becoming invented empty results.

Artwork palette queries accept a `spotify:image:` URI or a current Spotify CDN
image URL, including `i.scdn.co` and `image-cdn-*.spotifycdn.com`:

```python
colors = await spotify.get_colors(image_url)
print(colors.raw, colors.dark, colors.light)
```

Call this inside the open catalogue scope. Existing artwork models also contain
palette data when Spotify includes it; accessing those fields performs no I/O.

## Independent batch failures

```python
from spotapi import Public

outcomes = await Public.fetch_many([
    "spotify:track:4uLU6hMCjMI75M1A2tKUQC",
    "not a valid resource",
])
for item in outcomes:
    if item.ok:
        print(item.result)
    else:
        print(item.index, type(item.error).__name__)
```

Run inside an async function. Outcomes preserve input order and duplicate inputs.
`unwrap()` returns the value or raises that input's original exception.
Cancellation propagates. Worker tasks and active requests are bounded by
`concurrency`; this is for independent reads, never mutations.

Existing `get_tracks`, `get_albums` and `get_artists` remain strict: one failed
input fails the overall call. For typed bare IDs with per-item errors:

```python
from spotapi import fetch_many

outcomes = await fetch_many(track_ids, spotify.get_track, concurrency=5)
```

## Public embeds and published previews

```python
from spotapi import Public, Media

embed = await Public.get_embed("spotify:track:4uLU6hMCjMI75M1A2tKUQC")
print(embed.name, embed.preview_url)
await Media().download_cover(embed, "cover.jpg")
if embed.preview_url is not None:
    await Media().download_preview(embed, "preview.mp3")
```

The downloader opens an isolated unauthenticated transport, accepts Spotify CDN
hosts, disables redirects, validates media types and caps response bytes even
without Content-Length. Output is an explicit file path and cannot already
exist. Parent directories must exist. Published previews may be unavailable;
these methods never retrieve full track audio.

For optional MP3 artwork/title tags, install `spotapi[media]` and pass
`embed_cover=True` to `download_preview`. A tagging failure raises and leaves the
downloaded preview available. A file write already dispatched to a worker thread
may finish after cancellation. This does not grant redistribution rights.

For Canvas, fetch `canvas = await spotify.get_canvas(track)` and, when it is not
None, pass it to `Media().download_canvas(canvas, "canvas.mp4")`.

`lookup()` can fall back from a rich anonymous catalogue read to an `Embed`:

```python
from spotapi import Embed, Public

result = await Public.lookup(track_url)
if isinstance(result, Embed):
    print("Sparse embed metadata:", result.name)
```

Check the result type. Missing detailed fields are not synthesized. Account
failures do not fall back anonymously. Use `fallback=False` to disable this
behavior. `Public.get_track` and other rich getters retain their strict contracts.
`Public.get_embed(value, browser=True)` is an explicit optional browser-backed
alternative; install `spotapi[browser]` and `playwright install chromium` first.
It does not solve challenges or bypass browser security warnings.

## Podcast captions

```python
import os
from spotapi import AsyncClient, Transcripts

async def captions(episode_url):
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        transcript = await Transcripts(client).get(episode_url)
        for line in transcript.lines:
            print(line.start_time_ms, line.text)
```

Availability depends on the episode, account and region. Missing captions can
raise HTTPError; malformed cue envelopes raise BaseClientError. Offsets are
milliseconds. Speaker headings are omitted, timed fallback/music cues retained.
No audio is sent to an external transcription provider.

`Catalogue(client).get_transcript(...)` works inside an open authenticated
catalogue. Account helpers expose `account.transcripts.get(...)` and
`account.lyrics.get(...)`; lyrics remain subject to Spotify entitlement.

## Optional browser login and saved sessions

```sh
python -m pip install -e ".[browser,keyring]"
python -m playwright install chromium
```

```python
from spotapi import SavedSession, browser_login

async def connect():
    saved = SavedSession("personal")
    client = await browser_login(saved=saved)
    try:
        print(saved.info())  # presence only, never the cookie
    finally:
        await client.close()
```

The user signs into Spotify's browser window. SpotAPI does not collect a
password. Persistence is explicit and uses the OS credential store; there is
no plaintext-file fallback. Headless later runs can use `await saved.open()`.
`saved.info().present` does not prove validity; authorization checks it.
`saved.clear()` removes that named credential. A supported keyring backend is
required. Keep `browser_login()` separate from ordinary anonymous reads.

## Anonymous response caching

```python
from spotapi import Catalogue, ResponseCache

async with Catalogue(cache=ResponseCache(".spotapi-cache", ttl=3600)) as spotify:
    track = await spotify.get_track(track_url)
```

This is opt-in and limited to an allowlist of public metadata operations. An
authenticated client or injected query owner cannot enable this cache. Cookies,
headers, account operations and token-bearing embed HTML are not stored by the
catalogue. Language/proxy configurations partition entries. Memory retention and
individual payload size are bounded; the caller manages persistent disk storage.
Corrupt/expired entries are misses. Do not enable caching when freshness matters.

## Local MCP tools

```sh
python -m pip install -e ".[mcp]"
python -m spotapi.mcp
```

The command serves **stdio** and waits for an MCP host. It opens no HTTP port.
Configure your host to launch the Python interpreter where the extra is installed:

```json
{
  "mcpServers": {
    "spotapi": {
      "command": "python",
      "args": ["-m", "spotapi.mcp"]
    }
  }
}
```

Tools cover public lookups, search, batches, discovery, chart shortcuts,
first-page playlist occurrences and track visuals. The resource template is
`spotify://resource/{kind}/{identifier}`. Metadata is untrusted external content,
not an instruction to execute. No mutation or arbitrary file-download tool is
exposed. Account cookies are not accepted as tool arguments.

To enable caption tools, explicitly launch with `--authenticated` and configure
`SPOTIFY_COOKIE` in the host process environment. Do not share that configuration
or put credentials in a repository. It enables account-backed reads for the
connected host; only do so for a host you trust.

Build a local container with `docker build -f Dockerfile.mcp -t spotapi-mcp .`,
then launch `docker run --rm -i spotapi-mcp`. The Docker context excludes local
credentials and research files. No registry image has been published by this
configuration. Browser/keyring integrations are not included in that image.

## CLI equivalents

```sh
spotapi charts
spotapi chart top-50-global
spotapi events ARTIST_ID
spotapi similar-albums TRACK_ID
spotapi colors SPOTIFY_IMAGE_URI
spotapi embed SPOTIFY_TRACK_URL
spotapi transcript EPISODE_ID
spotapi lyrics TRACK_ID
spotapi download preview SPOTIFY_TRACK_URL --output preview.mp3
```

Replace uppercase placeholders. Captions require `SPOTIFY_COOKIE`; anonymous
commands do not. Download commands require a typed URL or URI. These additions
do not change the single-attempt policy for account mutations.
