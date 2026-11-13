---
description: Install SpotAPI and fetch your first Spotify result in Python. No developer dashboard or API key for public catalogue data.
---

# Your first result

Python 3.11 or newer is required. Public catalogue reads do not require a Spotify
login or developer app. These examples do not download full songs.

```sh
python -m pip install spotapi
spotapi search "Daft Punk"
```

Save the following as `first_result.py`, then run `python first_result.py`:

```python
import asyncio

from spotapi import Public


async def main() -> None:
    results = await Public.search("Daft Punk", types="track", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)


asyncio.run(main())
```

Track titles and ordering come from Spotify and may change. An empty search is
a valid result; a network or protocol failure raises a library exception.
First-time setup reads Spotify's current web-player metadata. Less common
operations can need additional discovery; query hashes are cached for that
Spotify build. Reusing a `Catalogue` avoids repeating session setup.

## Browse from your terminal

Install the optional keyboard-driven browser:

```sh
python -m pip install "spotapi[demo]"
spotapi discover "Daft Punk"
```

No account is needed. Paste a public Spotify link, inspect artwork and metadata,
or copy typed results as JSON. The optional interface uses the same catalogue
API as your Python application. Plain `spotapi search` needs no demo dependencies.

Run `spotapi --version` if the available commands do not match this guide. An
older executable on `PATH` can otherwise look like the current installation.

## Reuse connections

```python
from spotapi import Catalogue


async def explore() -> None:
    async with Catalogue() as spotify:
        results = await spotify.search("Daft Punk", types="artist", limit=5)
        if results.artists:
            artist = await spotify.get_artist(results.artists[0].uri)
            print(artist.name)
```

Call `await explore()` from an async application or `asyncio.run(explore())` from
a script. Use `Public` for one-shot work and `Catalogue` for related operations.

## Synchronous scripts

```python
from spotapi import SyncCatalogue

with SyncCatalogue() as spotify:
    results = spotify.search("Daft Punk", types="track", limit=5)
    for track in results.tracks:
        print(track.name)
```

`SyncCatalogue` owns one event loop in its creating thread. Inside an existing
async event loop, including many notebook environments, use `await Public.search`
or `async with Catalogue()` instead. The sync facade reuses the async core.

## JSON export

```python
import asyncio
import json

from spotapi import Public, to_dict


async def main() -> None:
    results = await Public.search("Daft Punk", types="track", limit=5)
    print(json.dumps(to_dict(results), indent=2))


asyncio.run(main())
```

Export uses Python field names and ISO dates. Unsupported values raise rather
than silently becoming strings. Explicitly exporting account models includes
their personal fields: review the output before sharing it.

## Explore Studio, then build your own

[Studio](studio.md) is an optional desktop application. Install
`spotapi[studio]` and run `spotapi studio`. Browse it to see catalogue results, account scopes and
player events together. Its [Python source](https://github.com/Aran404/SpotAPI/tree/main/spotapi/_studio)
uses the same library available to your application.

You can skip any stage: the CLI, terminal browser and Studio are examples,
not prerequisites. Start a real application by reusing a `Catalogue`, choosing
one workflow from [the catalogue guide](catalogue.md), and keeping network calls
inside explicit async functions.

For small, complete scripts, see
[search and artist lookup](https://github.com/Aran404/SpotAPI/blob/main/examples/public_search.py)
and [playlist metadata export](https://github.com/Aran404/SpotAPI/blob/main/examples/export.py).

## Install from source

Contributors can run the current repository and its examples by cloning it and
installing from the repository root:

```sh
python -m pip install -e .
```

See [discovery](discovery.md) for previews, charts, partial batches, captions,
optional browser login and MCP setup, or [the API reference](reference.md).
