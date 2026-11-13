# Migrating from SpotAPI 1.2.8

SpotAPI 2 is a rewrite, not a drop-in update. The published 1.2.8 package was
synchronous, split features across classes such as `Song`, `Artist` and
`PublicPlaylist`, and returned Spotify's nested dictionaries. SpotAPI 2 has an
async core, typed results and explicit client lifetimes. It also provides
`SyncCatalogue` for ordinary synchronous scripts.

This guide compares the published `spotapi==1.2.8` wheel with SpotAPI 2. It does
not describe the unpublished `async-v2` development branch.

## Decide whether to migrate

Use a fresh virtual environment for either version. Keep 1.2.8 pinned while you
migrate an existing application:

```sh
python -m pip install "spotapi==1.2.8"
```

Install the current release in the new environment:

```sh
python -m pip install "spotapi>=2,<3"
```

SpotAPI 2 requires Python 3.11 or newer.

## Why migrate?

These are observable API differences, not performance claims.

| Area | SpotAPI 1.2.8 | SpotAPI 2 |
|---|---|---|
| I/O model | Synchronous feature classes | Async-native API, plus the `SyncCatalogue` facade |
| Results | Raw nested mappings | Typed models with attributes and explicit optional fields |
| Connection ownership | Feature objects and a global public client pool | `async with` / `with` scopes with deterministic cleanup |
| Public catalogue | Tracks, artists, albums, playlists, podcasts and episodes | Those resources plus audiobooks, chapters, profiles, charts, concerts, radio, credits, Canvas, colors, transcripts and embeds |
| Search | Separate class methods and raw search envelopes | One typed multi-category search with category-specific helpers and iterators |
| Account access | Email/password `Login`, mutable feature objects and bundled CAPTCHA vendors | Cookie or browser login, composed account helpers and a provider-neutral CAPTCHA protocol |
| Player | Synchronous controls and a threaded event listener | Async controls, typed state, reconnecting event scopes, `wait_for` and explicit shutdown |
| Playlist edits | Stateful playlist IDs and raw mappings | Typed playlists and occurrence-aware edits using Spotify item UIDs |
| Tooling | Python API only | Scriptable CLI, optional Discover TUI, Studio desktop app and MCP server |

The wider surface does not make every v1 workflow portable. SpotAPI 2 does not
retain v1's account registration, family-membership automation, email/password
login, database saver classes, or bundled Capsolver/Capmonster clients. Use an
existing Spotify session for authenticated v2 features. If your application
depends on a removed workflow, keep 1.2.8 isolated until you replace it.

## Search

Version 1.2.8 returned Spotify's raw search envelope:

```python
from spotapi import Song

songs = Song().query_songs("weezer", limit=20)
items = songs["data"]["searchV2"]["tracksV2"]["items"]
for item in items:
    print(item["item"]["data"]["name"])
```

The native SpotAPI 2 API is asynchronous and returns typed results:

```python
import asyncio

from spotapi import Public


async def main() -> None:
    results = await Public.search("weezer", types="track", limit=20)
    for track in results.tracks:
        print(track.name, track.uri)


asyncio.run(main())
```

For a synchronous script, use the same result models through
`SyncCatalogue`:

```python
from spotapi import SyncCatalogue

with SyncCatalogue() as spotify:
    results = spotify.search("weezer", types="track", limit=20)
    for track in results.tracks:
        print(track.name, track.uri)
```

Do not use `SyncCatalogue` from a running event loop. In async applications and
notebooks with an active loop, use `await Public.search(...)` or
`async with Catalogue()`.

## Common public operations

| 1.2.8 | SpotAPI 2 async | SpotAPI 2 sync |
|---|---|---|
| `Song().query_songs(query, limit=20)` | `await Public.search(query, types="track", limit=20)` | `spotify.search(query, types="track", limit=20)` |
| `Song().paginate_songs(query)` | `async for track in Public.iter_tracks(query)` | Not exposed as an unbounded iterator; page with the async API when needed |
| `Song().get_track_info(track_id)` | `await Public.get_track(track_id)` | `spotify.get_track(track_id)` |
| `Artist().query_artists(query, limit=20)` | `await Public.search(query, types="artist", limit=20)` | `spotify.search(query, types="artist", limit=20)` |
| `Artist().get_artist(artist_id)` | `await Public.get_artist(artist_id)` | `spotify.get_artist(artist_id)` |
| `PublicAlbum(album_id).get_album_info()` | `await Public.get_album(album_id)` | `spotify.get_album(album_id)` |
| `PublicPlaylist(playlist_id).get_playlist_info()` | `await Public.get_playlist(playlist_id)` | `spotify.get_playlist(playlist_id)` |
| `Podcast(podcast_id).get_podcast_info()` | `await Public.get_podcast(podcast_id)` | `spotify.get_podcast(podcast_id)` |
| `Podcast().get_episode(episode_id)` | `await Public.get_podcast_episode(episode_id)` | `spotify.get_podcast_episode(episode_id)` |

IDs, Spotify URIs and open.spotify.com URLs are accepted by the documented v2
lookup methods. Returned models are values: reading `track.name` performs no
network request. Use `spotapi.to_dict()` when an application needs JSON-safe
dictionaries.

## Reuse connections

`Public` is convenient for unrelated one-shot calls. Reuse a `Catalogue` when
several operations belong to one workflow:

```python
from spotapi import Catalogue


async def inspect_artist(artist_uri: str) -> None:
    async with Catalogue() as spotify:
        artist = await spotify.get_artist(artist_uri)
        top_tracks = await spotify.get_artist_top_tracks(artist.uri)
        print(artist.name, len(top_tracks))
```

Page iterators are async generators. If a loop may stop early, close it
explicitly with `contextlib.aclosing`.

## Authentication and account features

Version 1.2.8 constructed `Login` from an email or username, password, solver
configuration and an optional saver. SpotAPI 2 does not accept account
passwords. It uses an existing Spotify web session:

```python
import os

from spotapi import Private


async def show_profile() -> None:
    async with Private.from_cookies(os.environ["SPOTIFY_COOKIE"]) as account:
        profile = await account.get_profile()
        print(profile)
```

For an interactive application, use `browser_login()` with `SavedSession`
instead of collecting credentials. Never print, commit or send the Spotify
cookie to another service.

Authenticated helpers borrow their client. The surrounding `Private` or
`AsyncClient` context owns token refresh, transports and shutdown. Playlist and
player mutations are not automatically replayed after an ambiguous failure;
read the resulting state before deciding whether to retry.

## Player events and controls

The v1 `Player` and `EventManager` were synchronous and built on a background
listener. V2 event callbacks and controls are async and live inside an explicit
connection scope:

```python
from spotapi import AsyncClient, Player


async def watch_player(cookie: str) -> None:
    async with await AsyncClient.from_cookies(cookie) as client:
        player = Player(client)

        @player.event
        async def on_track_change(before, after) -> None:
            if after is not None:
                print(after.artist, after.name)

        async with player.connect():
            await player.pause()
            await player.resume()
```

Important renames include `skip_next()` to `next()`, `skip_prev()` to
`previous()`, `seek_to()` to `seek()`, `set_shuffle()` to `shuffle()`, and
`set_volume()` to `volume()`. V2 repeat mode is `"off"`, `"context"` or
`"track"`, rather than a boolean.

## Read next

- [First result](https://spotapi.readthedocs.io/en/latest/quickstart/)
- [Catalogue and search](https://spotapi.readthedocs.io/en/latest/catalogue/)
- [Accounts and playlists](https://spotapi.readthedocs.io/en/latest/account/)
- [Player controls and events](https://spotapi.readthedocs.io/en/latest/player/)
- [Python API reference](https://spotapi.readthedocs.io/en/latest/reference/)
