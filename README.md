<p align="center">
  <img src="https://raw.githubusercontent.com/Aran404/SpotAPI/main/spotapi/_studio/assets/logo.svg" width="84" height="84" alt="SpotAPI symbol">
</p>

<h1 align="center">SpotAPI</h1>
<p align="center"><b>Spotify for Python. Async, typed, and no API key for public data.</b></p>
<p align="center">
  <a href="#first-search">Start</a> ·
  <a href="#see-it-in-action">Demos</a> ·
  <a href="#studio">Studio</a> ·
  <a href="#build-it-into-your-app">Integrate</a> ·
  <a href="https://spotapi.readthedocs.io/">Docs</a>
</p>

---

Search the Spotify catalogue from your terminal, or build a Python app on top of
fully typed async results. Start with public data, no signup and no developer
dashboard. Connect your account later for saved music, playlist editing and live
player events.

> **SpotAPI 2 is a breaking async release.** Synchronous projects can pin
> `spotapi==1.2.8`. See the [migration guide](https://github.com/Aran404/SpotAPI/blob/main/MIGRATION.md)
> and the [release checks](https://spotapi.readthedocs.io/en/latest/release-checks/).

## First search

Requires Python 3.11 or newer.

```bash
python -m pip install spotapi
spotapi search "Daft Punk"
```

No key, no login, no config. The first request discovers Spotify's current
web-player queries; this can take longer on a cold cache. Later runs reuse
queries cached for the same Spotify build.

Next, [browse with Discover](#see-it-in-action), [open Studio](#studio), or start
building directly in Python:

```python
import asyncio
from spotapi import Public


async def main() -> None:
    results = await Public.search("Daft Punk", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)


asyncio.run(main())
```

`Public` searches ten categories, resolves Spotify links and streams tracks from
public playlists. It cleans up its own connections.

## Why SpotAPI

- **No API key for public data.** Search, lookups, credits and public playlists work anonymously.
- **Typed and async.** Every result is a model you can autocomplete, not a dict you have to guess at.
- **No surprises.** Reading a model never triggers a hidden HTTP request. Optional metadata stays optional.
- **Duplicate-aware playlists.** Edit one occurrence of a track without touching its twin.
- **Your account when you want it.** Liked songs, rankings, playlist edits and live player events.
- **A CLI that does real work.** Search, credits, playlists, library and player control from one command.
- **No developer dashboard setup.** No Client ID, no Premium requirement and no user cap for public data. [See the comparison](#spotapi-vs-the-official-web-api).

## See it in action

Browse search results, artwork and typed data directly from your terminal:

![SpotAPI Discover turns one terminal command into browsable Spotify results and typed data](https://raw.githubusercontent.com/Aran404/SpotAPI/main/assets/cli-demo.gif)

```bash
python -m pip install "spotapi[demo]"
spotapi discover "Daft Punk"
```

| Demo | What you get | Run it |
|---|---|---|
| **[Discover](https://github.com/Aran404/SpotAPI/blob/main/examples/discover.py)** | A keyboard-driven terminal UI for browsing Spotify's public search. No login. **Start here.** | `spotapi discover "Daft Punk"` |
| **[Mix map](https://github.com/Aran404/SpotAPI/blob/main/examples/mix_map.py)** | Finds harmonically compatible transitions in a public playlist and tells you how far to shift the incoming track's tempo. | `python -m examples.mix_map` |

Discover accepts a search query or Spotify link. Mix map runs from a clone of
the repository and accepts your own public playlist link. Tempo and key data
depend on what Spotify supplies; missing analysis stays unknown.

## Studio

Open a track, read its credits, follow links into artists and albums, or expand
the typed data behind every view. Studio also shows public lyrics and can seek to
a timed line on a connected Spotify player.

![SpotAPI Studio: the listening desk](https://raw.githubusercontent.com/Aran404/SpotAPI/main/examples/studio/preview.png)

```bash
python -m pip install "spotapi[studio]"
spotapi studio
```

Studio uses your platform's native WebView; see the [platform setup](https://spotapi.readthedocs.io/en/latest/studio/).

Use **Connect Spotify** to sign in through Spotify's normal login window, or set
`SPOTIFY_COOKIE` in a local `.env`. Cookies stay in Python. Playback controls an
existing Spotify device; Studio does not render audio.

[Studio guide](https://spotapi.readthedocs.io/en/latest/studio/) ·
[Small examples](https://github.com/Aran404/SpotAPI/tree/main/examples)

## Go beyond search

The CLI also looks up credits, lists playlist occurrences, manages liked tracks
and controls an existing Spotify player:

```bash
spotapi search "Daft Punk" --type artist --json
spotapi get SPOTIFY_URL
spotapi credits 0DiWol3AO6WpXZgp0goxAV
spotapi playlist items PLAYLIST_ID --limit 10
spotapi library list
spotapi player status
```

`search` and `get` work anonymously. Library and player commands, playlist edits
and `playlist items --private` read `SPOTIFY_COOKIE` from your environment. See
[sign-in setup](https://spotapi.readthedocs.io/en/latest/studio/#sign-in).

Run `spotapi playlist --help`, `spotapi library --help` or `spotapi player --help`
for every action. Playlist `remove` and `move` take occurrence IDs from
`playlist items`, so duplicate tracks can be edited individually.

## Build it into your app

Pick the idea closest to yours:

| Your idea | Start with |
|---|---|
| A DJ crate with tempo and harmonic keys | [Playlist crate](https://github.com/Aran404/SpotAPI/blob/main/examples/playlist_crate.py) |
| A public-data inspector | `spotapi discover` or `spotapi get SPOTIFY_URL` |
| A playlist discovery companion | `Public.get_radio()` · `Public.get_playlist_recommendations()` |
| Your own music dashboard | [Account, rankings and saved music](https://spotapi.readthedocs.io/en/latest/account/) |
| A duplicate-aware playlist curator | `Playlist.items()` · `Playlist.move_occurrences()` · `Playlist.remove_occurrences()` |
| A live now-playing display | [Player example](https://github.com/Aran404/SpotAPI/blob/main/examples/player.py) · [Lyrics example](https://github.com/Aran404/SpotAPI/blob/main/examples/lyrics.py) |

### Public data: reuse one `Catalogue`

For several operations, share a single context inside your async application:

```python
from spotapi import Catalogue

async with Catalogue() as spotify:
    results = await spotify.search("Daft Punk")
    if results.artists:
        artist = await spotify.get_artist(results.artists[0].uri)
        print(artist.name)
```

### Your own account: `Private`

`Private` opens and closes the authenticated session for you:

```python
import os

from spotapi import Private

async with Private.from_cookies(os.environ["SPOTIFY_COOKIE"]) as spotify:
    favorites = await spotify.stats.get(time_range="medium_term", limit=5)
    for track in favorites.tracks:
        print(track.name)
```

### Production details

- Import result types from `spotapi.models`.
- Catch `SpotAPIError` for library failures.
- Use `AsyncClient` directly to share transports and configure connection options.
- See the guides for ownership, cancellation and explicit mutations.

## SpotAPI vs the official Web API

In February 2026, Spotify [tightened Development Mode](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security)
for its official Web API. Libraries built on that API, such as Spotipy, work
within those limits. SpotAPI uses Spotify's web-player endpoints without a
developer app. These endpoints have their own rate limits, authentication
requirements and changing response contracts.

| | Official Web API (Development Mode) | SpotAPI, public data |
|---|---|---|
| Developer app / Client ID | Required; **up to 25 apps per developer** | Not needed |
| Spotify account | **App owner needs Premium** in Development Mode | Not needed |
| Authorized users | **Up to five** per Client ID | No cap to manage |
| Intended use | Non-commercial personal projects and learning | Your call, subject to the [legal notice](https://github.com/Aran404/SpotAPI/blob/main/LEGAL_NOTICE.md) |
| Setup | Create an app, then wire up credentials | `pip install spotapi` |

Choose based on the endpoints and authentication your application needs.
SpotAPI relies on unofficial web-player contracts; see the
[verification boundaries](https://spotapi.readthedocs.io/en/latest/release-checks/#boundaries) before integrating.

<sub>Checked against Spotify's [migration guide](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide)
and [July 2026 update](https://developer.spotify.com/documentation/web-api/references/changes/july-2026).
The app owner needs Premium in Development Mode. Existing apps can retain
previously authorized user counts above five; Extended Quota Mode differs.
Development Mode apps share their developer account's quota.</sub>

## Guides

Read the [complete rendered documentation](https://spotapi.readthedocs.io/), or
jump directly to a guide:

[First result](https://spotapi.readthedocs.io/en/latest/quickstart/) ·
[Coming from Spotipy](https://spotapi.readthedocs.io/en/latest/from-spotipy/) ·
[Discovery, previews and captions](https://spotapi.readthedocs.io/en/latest/discovery/) ·
[Python API reference](https://spotapi.readthedocs.io/en/latest/reference/)


[Catalogue](https://spotapi.readthedocs.io/en/latest/catalogue/) ·
[Account](https://spotapi.readthedocs.io/en/latest/account/) ·
[Player](https://spotapi.readthedocs.io/en/latest/player/) ·
[Request policy](https://spotapi.readthedocs.io/en/latest/transport/) ·
[API layout](https://spotapi.readthedocs.io/en/latest/api-layout/) ·
[Migration from v1](https://github.com/Aran404/SpotAPI/blob/main/MIGRATION.md)

## Sponsorship

Support SpotAPI's maintenance, testing and documentation. Sponsors receive a
clearly labeled placement here and, where useful, in a relevant guide.

Choose a supporter listing, featured placement, README category exclusivity,
or an optional integration partnership such as a CAPTCHA-provider adapter. Users keep their choice of provider; paid
services are never required for ordinary public-data workflows.

Contact [aran.inbox.personal@gmail.com](mailto:aran.inbox.personal@gmail.com)
to discuss a placement and arrange payment directly through PayPal.
See [sponsorship details](https://github.com/Aran404/SpotAPI/blob/main/SPONSORSHIP.md).

## Contributing

[Contributing](https://github.com/Aran404/SpotAPI/blob/main/CONTRIBUTING.md) ·
[Tests](https://github.com/Aran404/SpotAPI/blob/main/tests/README.md) ·
[Release review](https://spotapi.readthedocs.io/en/latest/release-checks/) ·
[Legal notice](https://github.com/Aran404/SpotAPI/blob/main/LEGAL_NOTICE.md) ·
[GPL-3.0](https://github.com/Aran404/SpotAPI/blob/main/LICENSE)

If SpotAPI helps you build something, star the repository or share what you built.
