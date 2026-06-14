# Migrating from SpotAPI v1 to v2

SpotAPI v2 is a full async rewrite. This guide covers every breaking change
and shows the equivalent v2 pattern for each v1 pattern.

---

## Installation

```bash
# Remove v1
pip uninstall spotapi

# Install v2 beta
pip install "spotapi==2.0.0b1"
```

---

## Breaking changes at a glance

| Area | v1 | v2 |
|---|---|---|
| I/O model | Synchronous | Fully `async`/`await` |
| Search generators | `for page in gen:` | `async for page in gen:` |
| Return types | Raw `dict` / `Mapping` | Typed dataclasses (`Track`, `Artist`, …) |
| Auth | CAPTCHA solver required | TOTP — no solver needed |
| Config object | `Config(solver=…, logger=…)` | No config class — pass logger where needed |
| Session saving | `instance.save(MongoSaver())` | Not yet implemented in v2 beta |
| Namespace | `from spotapi import Song` | `from spotapi.v2.public import Public` |
| Python version | 3.11+ | **3.11+** |

---

## Search

### Tracks

```python
# v1
from spotapi import Song

song = Song()
for batch in song.paginate_songs("weezer"):
    for item in batch:
        print(item["item"]["data"]["name"])

# v2
import asyncio
from spotapi.v2.public import Public

async def main() -> None:
    async for page in Public.search_tracks("weezer"):
        for track in page:
            print(track.name)

asyncio.run(main())
```

### Artists

```python
# v1
from spotapi import Song
# (no dedicated artist search in v1 public API)

# v2
from spotapi.v2.public import Public

async for page in Public.search_artists("Radiohead"):
    for artist in page:
        print(artist.profile.name, artist.uri)
```

### Albums

```python
# v2
from spotapi.v2.public import Public

async for page in Public.search_albums("OK Computer"):
    for album in page:
        print(album.name, album.date.year)
```

### Playlists

```python
# v2
from spotapi.v2.public import Public

async for page in Public.search_playlists("chill vibes"):
    for playlist in page:
        print(playlist.name, playlist.owner_spotapi.v2.data.name)
```

### Podcasts

```python
# v2
from spotapi.v2.public import Public

async for page in Public.search_podcasts("tech"):
    for podcast in page:
        print(podcast.name, podcast.publisher.name)
```

---

## Authentication

```python
# v1
from spotapi import Login, Config, solver_clients

cfg = Config(
    solver=solver_clients.Capsolver("YOUR_API_KEY"),
)
instance = Login(cfg, "YOUR_PASSWORD", email="YOUR_EMAIL")
instance.login()

# v2
# Authentication against private endpoints is planned for spotapi.v2.0.0 stable.
# The v2 beta currently covers public (unauthenticated) search.
# TOTP-based token acquisition happens automatically via AuthSession.authorize().
```

---

## Loggers

```python
# v1
from spotapi import NoopLogger

# v2
from spotapi.v2.types import NoopLogger, LoggerColour, JsonLogger, Level

logger = LoggerColour(min_level=Level.INFO)
noop   = NoopLogger()
```

---

## Data access

v1 returned raw dicts — you accessed fields via string keys and had to know
the Spotify response shape yourself:

```python
# v1
item["item"]["data"]["name"]
item["item"]["data"]["artists"]["items"][0]["profile"]["name"]
```

v2 returns typed dataclasses so your editor can autocomplete the fields:

```python
# v2
track.name
track.artists.items[0].profile.name
track.duration.total_milliseconds // 1000   # seconds
track.playability.playable
```

---

## Features not yet in v2 beta

The following v1 features are planned for the stable v2 release and are not
available on the `async-v2` branch yet:

- Private playlist management (`PrivatePlaylist`)
- Session savers (`MongoSaver`, `JSONSaver`, `RedisSaver`)
- Player control (`Player`)
- Family plan management (`Family`)
- Password reset (`Password`)
- User profile (`User`)
- WebSocket event streaming (`Status`)
- More...

If you depend on any of these, stay on v1 (`pip install "spotapi<2"`).