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

Search the catalogue, follow song credits, explore radio, and work with playlists.
Connect your account for saved music, personal rankings and a live player with
async event listeners. Results are typed dataclasses; pagination stays lazy.

**v2 beta.** Install from this checkout to try the rewrite.
Spotify's unofficial endpoints can change. [Release checks and limits](docs/release-2.0.0b3.md).

[Sponsor SpotAPI](SPONSORSHIP.md) · Monthly placements with category exclusivity available.

## Quickstart

Requires Python 3.11 or newer.

```bash
python -m pip install -e .
```

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

## Build with it

| Your idea | Start with |
|---|---|
| A DJ crate with tempo and harmonic keys | [Playlist crate](examples/playlist_crate.py) |
| A credits rabbit hole | [Song credits](examples/credits.py) |
| A playlist discovery companion | `Public.get_radio()` · `Public.get_playlist_recommendations()` |
| Your own music dashboard | [Account, rankings and saved music](docs/account.md) |
| A duplicate-aware playlist curator | `Playlist.items()` · `Playlist.remove_occurrences()` |
| A player or live lyrics display | [Player events](docs/player.md) · [Lyrics example](examples/lyrics.py) |

For several operations, reuse a `Catalogue` context. Inside your async application:

```python
from spotapi import Catalogue

async with Catalogue() as spotify:
    results = await spotify.search("Daft Punk")
    artist = await spotify.get_artist(results.artists[0].uri)
```

Authenticated helpers accept the same client. One context owns authentication,
refresh tasks and HTTP connections:

```python
from spotapi import Account, AsyncClient

async with await AsyncClient.from_cookies(cookie) as client:
    favorites = await Account(client).stats.get(time_range="medium_term", limit=5)
```

Import result types from `spotapi.models`. Optional metadata stays optional, and
reading a model never makes hidden HTTP requests. Catch `SpotAPIError` for library
failures. See the guides for ownership, cancellation and explicit mutations.

## Guides

[Catalogue](docs/catalogue.md) · [Account](docs/account.md) · [Player](docs/player.md) ·
[API layout](docs/api-layout.md) · [Migration from v1](MIGRATION.md)

[Contributing](CONTRIBUTING.md) · [Tests](tests/README.md) · [Release review](docs/release-2.0.0b3.md) ·
[Legal notice](LEGAL_NOTICE.md) · [GPL-3.0](LICENSE)

If SpotAPI helps you build something, a star helps other developers find it.

## Sponsorship

Sponsor SpotAPI's maintenance and development. Monthly placements include a
labeled spot above Quickstart and, where relevant, a link in the guide your
customers would use. Category exclusivity is available by agreement.

Contact [aran.inbox.personal@gmail.com](mailto:aran.inbox.personal@gmail.com)
to discuss a placement and arrange payment directly through PayPal.
See [sponsorship details](SPONSORSHIP.md).
