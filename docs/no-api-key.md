---
description: Search Spotify from Python without a developer API key. Install SpotAPI, get typed track data, reuse async clients and export public metadata.
---

# Search Spotify in Python without an API key

You can read **public Spotify catalogue metadata** with SpotAPI without creating a Spotify developer application, requesting OAuth client credentials or logging in. SpotAPI is an **unofficial**, typed, asynchronous Python library; its requests depend on Spotify's web-player interfaces and can change when Spotify changes them.

Python 3.11 or newer is required. Install from PyPI:

```sh
python -m pip install -U spotapi
```

## 1. Search for tracks in Python

Save this as `search_spotify.py` and run `python search_spotify.py`:

```python
import asyncio

from spotapi import Public


async def main() -> None:
    results = await Public.search("Daft Punk", types="track", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)


asyncio.run(main())
```

The `tracks` are **typed models**, not raw dictionaries. An empty result is valid; network and protocol failures are raised rather than silently becoming empty results. This reads metadata, **not audio bytes**.

Prefer to try it without writing Python? The base installation also provides a CLI:

```sh
python -m spotapi search "Daft Punk"
```

## 2. Reuse a connection to inspect a track

For applications making several related requests, share a `Catalogue` rather than creating a separate client for every item:

```python
import asyncio

from spotapi import Catalogue


async def main() -> None:
    async with Catalogue() as spotify:
        results = await spotify.search("Daft Punk", types="track", limit=5)
        if not results.tracks:
            print("No matching tracks")
            return

        track = await spotify.get_track(results.tracks[0].uri)
        print(track.name, track.uri)


asyncio.run(main())
```

The first operation may take longer because SpotAPI discovers the current web-player queries. Reusing the connection reduces repeated setup; query data is cached for the current Spotify build. Do not treat this as a guarantee of stable Spotify endpoints or unlimited request volume.

## 3. Export public search results as JSON

```python
import asyncio
import json

from spotapi import Public, to_dict


async def main() -> None:
    results = await Public.search("Daft Punk", types="track", limit=5)
    print(json.dumps(to_dict(results), ensure_ascii=False, indent=2))


asyncio.run(main())
```

For public playlists, the [playlist audit and CSV export example](https://github.com/Aran404/SpotAPI/blob/main/examples/playlist_audit.py) handles pages, duplicates, unavailable entries and partial-write safety. It runs from a repository checkout and does not modify your playlists.

## What does and doesn't require credentials?

| Task | Spotify developer API key | Spotify account session |
|---|---|---|
| Public search, track and playlist metadata | Not needed | Not needed for accessible public data |
| Browse public results in Discover | Not needed | Not needed |
| Manage saved music or private playlists | Not needed | Required |
| Control an existing player | Not needed | Required, subject to device and account capabilities |
| Stream or download full tracks through SpotAPI | Not supported | Not supported |

SpotAPI does **not** stream, decrypt, or save Spotify audio. Account and player functions require your own Spotify session; they are not interchangeable with anonymous reads. Spotify's terms, API changes, regional availability and entitlement rules still apply. For applications that need Spotify's official OAuth contracts, consider [Spotipy and the official API](from-spotipy.md) instead.

## Troubleshooting first-run errors

- Check the interpreter and installed version: `python --version`, `python -m pip show spotapi` and `python -m spotapi --version`.
- If `spotapi` isn't on your PATH, use `python -m spotapi`. On Windows, `py -m ...` may be appropriate if that's how you installed Python.
- First-run searches can be slower while query definitions are discovered. A subsequent error still needs investigation; don't retry indefinitely.
- Public search needs no `SPOTIFY_COOKIE`. Never paste a real cookie or authorization token into GitHub issues or screenshots.

See [the quickstart](quickstart.md), [troubleshooting](troubleshooting.md), and [the Python catalogue reference](catalogue.md).

If SpotAPI helped you build something, [star the open-source project](https://github.com/Aran404/SpotAPI) or share a working example with other Python developers.
