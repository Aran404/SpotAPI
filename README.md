<div align="center">

![alt text](image.png)

# SpotAPI v2

**The fully async Python client for Spotify's public & private API.**
No API key. No Premium. No rate-limit babysitting.

[![PyPI](https://img.shields.io/pypi/v/spotapi?color=1DB954&label=pypi)](https://pypi.org/project/spotapi/)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue)](https://python.org)
[![Async](https://img.shields.io/badge/asyncio-native-1DB954)](https://docs.python.org/3/library/asyncio.html)
[![Typed](https://img.shields.io/badge/typed-py.typed-%230075A8)](https://peps.python.org/pep-0561/)
[![License](https://img.shields.io/github/license/Aran404/SpotAPI)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Aran404/SpotAPI?style=social)](https://github.com/Aran404/SpotAPI/stargazers)

> ⚠️ **This is the `async-v2` beta branch.** It is under active development and the API may change before the stable `spotapi.v2.0.0` release. For the stable v1 library see [main](https://github.com/Aran404/SpotAPI/tree/main).

</div>

---

## What's new in v2

| | v1 | v2 |
|---|---|---|
| **I/O model** | Synchronous | Fully async (`asyncio`) |
| **Pagination** | `for page in gen:` | `async for page in gen:` |
| **Type safety** | Partial | Full — `py.typed`, typed data wrappers |
| **HTTP** | `tls-client` | `wreq` with connection pooling & retry |
| **Auth** | CAPTCHA solver required | TOTP-based (no solver needed) |
| **Session** | Manual refresh | Auto-refresh background task |
| **Codebase** | Flat structure | Layered: `connection/`, `datastruct/`, `specialized/` |

---

## Installation

```bash
# Latest beta
pip install "spotapi==2.0.0b1"

# Or directly from this branch
pip install "git+https://github.com/Aran404/SpotAPI@async-v2"
```

---

## Quick start

### Unauthenticated — public search

```python
import asyncio
import spotapi

async def main() -> None:
    async for page in spotapi.sync.Public.search_tracks("Radiohead"):
        for track in page:
            duration_s = track.duration.total_milliseconds // 1000
            print(f"{track.name}  ({duration_s}s)  —  {track.uri}")

asyncio.run(main())
```

### Search artists with pagination control

```python
import asyncio
import spotapi

async def main() -> None:
    # Yields one page (up to 100 results) at a time
    async for page in spotapi.sync.Public.search_artists("Tame Impala"):
        for artist in page:
            verified = artist.on_platform_reputation_trait.verification.is_verified
            print(f"{artist.profile.name}  verified={verified}")

asyncio.run(main())
```

### Search albums

```python
import asyncio
import spotapi

async def main() -> None:
    async for page in spotapi.sync.Public.search_albums("OK Computer"):
        for album in page:
            artists = ", ".join(a.profile.name for a in album.artists.items)
            print(f"{album.name} ({album.date.year}) — {artists}")

asyncio.run(main())
```

### Search podcasts

```python
import asyncio
import spotapi

async def main() -> None:
    async for page in spotapi.sync.Public.search_podcasts("Lex Fridman"):
        for podcast in page:
            print(f"{podcast.name} by {podcast.publisher.name}")

asyncio.run(main())
```

---

## Architecture overview

```
v2/
├── base.py                  # BaseClient — pathfinder query + pagination
├── client.py                # AsyncClient — thin HTTP facade + context manager
├── session.py               # BundleSession + AuthSession — tokens, TOTP, auto-refresh
├── public.py                # Public — typed search generators
│
├── connection/
│   ├── http.py              # HTTPClient — wreq wrapper, retry + backoff, browser emulation
│   ├── websocket.py         # WebSocketClient — heartbeat, event dispatch
│   └── types.py             # ResponseSuccess / ResponseFailure, backoff types
│
├── datastruct/
│   ├── object_dict.py       # ObjectDict — attribute-access dict for raw JSON
│   ├── pool.py              # Pool[T] — generic async object pool
│   └── event_handler.py     # EventDispatcher — async event system
│
├── specialized/
│   ├── totp.py              # TOTP generation — no CAPTCHA solver required
│   └── data_wrappers/
│       ├── _common.py       # Shared color/visual dataclasses
│       ├── track.py         # Track
│       ├── artist.py        # Artist
│       ├── album.py         # Album
│       ├── playlist.py      # Playlist
│       └── podcast.py       # Podcast
│
├── types/
│   ├── logger.py            # LoggerProtocol + 5 concrete loggers
│   └── exceptions.py        # HTTPError, WebsocketError, BaseClientError
│
└── utils/
    ├── cache.py             # timed_cache — TTL-based async/sync cache decorator
    ├── random.py            # Weighted random selection
    └── strings.py           # JS bundle parsing, hash extraction
```

---

## Logging

v2 ships five ready-to-use loggers. All implement `LoggerProtocol` so you can drop in your own.

```python
from spotapi.v2.types import LoggerColour, JsonLogger, NoopLogger, MultiLogger, Level

# Pretty coloured output to stderr (default)
logger = LoggerColour(min_level=Level.INFO)

# Structured JSON — good for log aggregation pipelines
json_logger = JsonLogger(min_level=Level.WARNING)

# Fan-out to multiple loggers at once
combined = MultiLogger(logger, json_logger)

# Silence everything
noop = NoopLogger()

# Bind extra context fields that appear on every subsequent record
scoped = logger.bind(request_id="abc123")
scoped.info("Token refreshed", token_version=2)
```

---

## Connection pool & browser emulation

Every `HTTPClient` automatically selects a randomised browser profile (Chrome, Edge, Firefox, Opera) weighted towards modern versions, and a randomised OS (Windows 30×, macOS 6×, Linux 2×). A shared `ClientPool` reuses connections across requests.

```python
from spotapi.v2.connection import HTTPClient, ClientPool

# Get a pooled client (shared across BaseClient instances)
http = await ClientPool.get()

# Or create a dedicated client with a proxy
async with HTTPClient(proxies=[wreq.Proxy.http("http://user:pass@host:port")]) as http:
    response = await http.get("https://open.spotify.com/")
```

---

## Migration from v1

For a full side-by-side comparison of the v1 and v2 APIs, see [MIGRATION.md](MIGRATION.md).

```python
# v1
from spotapi import Song
song = Song()
for batch in song.paginate_songs("weezer"):
    for item in batch:
        print(item["item"]["data"]["name"])

# v2
import spotapi
async for page in spotapi.sync.Public.search_tracks("weezer"):
    for track in page:
        print(track.name)
```

---

## Contributing

All contributions are welcome. The async rewrite is still in progress and there are plenty of well-scoped tasks available — see [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide and the open [good first issues](https://github.com/Aran404/SpotAPI/labels/good%20first%20issue).

```bash
git clone https://github.com/Aran404/SpotAPI
cd SpotAPI
git checkout async-v2
pip install -e ".[dev]"
```

---

## Legal notice

> **Disclaimer**: This repository is provided for educational purposes only. The author accepts no responsibility for misuse. Accessing private Spotify endpoints may violate Spotify's Terms of Service. Use responsibly. See [LEGAL_NOTICE.md](LEGAL_NOTICE.md) for full details.

---

## License

[GPL-3.0](LICENSE) © [Aran404](https://github.com/Aran404)