<p align="center">
  <img src="assets/logo.svg" width="84" height="84" alt="SpotAPI symbol">
</p>

<h1 align="center">SpotAPI</h1>
<p align="center">Async Spotify for Python. No API key for public data.</p>
<p align="center">
  <a href="#quickstart">Quickstart</a> ·
  <a href="#studio">Try Studio</a> ·
  <a href="#build-with-it">Build with it</a> ·
  <a href="#guides">Guides</a>
</p>

Search Spotify from your terminal or build a Python app with typed async results.
Start with the public catalogue, then connect your account for saved music,
playlist editing and live player events.

**SpotAPI 2** is a breaking async release. Synchronous projects can pin
`spotapi==1.2.8`. [Migration guide](MIGRATION.md) · [Release checks](docs/release-2.0.0.md)

[Sponsor SpotAPI](SPONSORSHIP.md) · Monthly placements with category exclusivity available.

## Quickstart

Requires Python 3.11 or newer.

```bash
python -m pip install spotapi
spotapi search "Daft Punk"
```

![Running spotapi search Daft Punk returns track names and Spotify URIs](assets/cli-demo.gif)

To try an unreleased checkout, run `python -m pip install -e .` from its root.

`spotapi get SPOTIFY_URL` prints details as JSON. Both commands work anonymously.

```python
import asyncio
from spotapi import Public


async def main() -> None:
    results = await Public.search("Daft Punk", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)


asyncio.run(main())
```

No login is needed. Search ten categories, resolve Spotify links, or stream tracks
from a public playlist. `Public` cleans up its connections for you.

## Studio

A small music workbench built on the same library: discovery, credits, your
collection, a live queue, lyrics and an interactive feature lab.

![SpotAPI Studio: the listening desk](examples/studio/preview.png)

```bash
python -m pip install -e ".[studio]"
python -m examples.studio
```

Use **Connect Spotify** to sign in through Spotify's normal login window, or set
`SPOTIFY_COOKIE` in a local `.env`. Cookies stay in Python. Playback controls an
existing Spotify device; Studio does not provide an audio renderer.

[Studio guide](docs/studio.md) · [Terminal inspector](examples/discover.py) · [Small examples](examples)

For a keyboard-driven catalogue browser, run these commands from the checkout:

```bash
python -m pip install -e ".[demo]"
python -m examples.discover "Daft Punk"
```

## Build with it

| Your idea | Start with |
|---|---|
| A DJ crate with tempo and harmonic keys | [Playlist crate](examples/playlist_crate.py) |
| A credits rabbit hole | [Song credits](examples/credits.py) |
| A playlist discovery companion | `Public.get_radio()` · `Public.get_playlist_recommendations()` |
| Your own music dashboard | [Account, rankings and saved music](docs/account.md) |
| A duplicate-aware playlist curator | `Playlist.items()` · `Playlist.move_occurrences()` · `Playlist.remove_occurrences()` |
| A live now-playing display | [Player example](examples/player.py) · [Lyrics example](examples/lyrics.py) |

For several operations, reuse a `Catalogue` context. Inside your async application:

```python
from spotapi import Catalogue

async with Catalogue() as spotify:
    results = await spotify.search("Daft Punk")
    artist = await spotify.get_artist(results.artists[0].uri)
```

For your own account, `Private` opens and closes the authenticated session:

```python
import os

from spotapi import Private

async with Private.from_cookies(os.environ["SPOTIFY_COOKIE"]) as spotify:
    favorites = await spotify.stats.get(time_range="medium_term", limit=5)
    for track in favorites.tracks:
        print(track.name)
```

See [sign-in setup](docs/studio.md#sign-in) for Studio login or a local cookie.
Use `AsyncClient` directly to share transports and configure connection options.

Import result types from `spotapi.models`. Optional metadata stays optional, and
reading a model never makes hidden HTTP requests. Catch `SpotAPIError` for library
failures. See the guides for ownership, cancellation and explicit mutations.

## Guides

[Catalogue](docs/catalogue.md) · [Account](docs/account.md) · [Player](docs/player.md) ·
[API layout](docs/api-layout.md) · [Migration from v1](MIGRATION.md)

[Contributing](CONTRIBUTING.md) · [Tests](tests/README.md) · [Release review](docs/release-2.0.0.md) ·
[Legal notice](LEGAL_NOTICE.md) · [GPL-3.0](LICENSE)

If SpotAPI helps you build something, a star helps other developers find it.

## Sponsorship

Sponsor SpotAPI's maintenance and development. Monthly placements include a
labeled spot above Quickstart and, where relevant, a link in the guide your
customers would use. Category exclusivity is available by agreement.

Contact [aran.inbox.personal@gmail.com](mailto:aran.inbox.personal@gmail.com)
to discuss a placement and arrange payment directly through PayPal.
See [sponsorship details](SPONSORSHIP.md).
