# Changelog

All notable changes to SpotAPI are documented here.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
SpotAPI adheres to [Semantic Versioning](https://semver.org/).

---

## [Unreleased] — `async-v2` beta

### Added

- **Full async rewrite** — every public method is now a coroutine or
  `AsyncGenerator`. No sync wrappers, no `asyncio.run()` hidden inside the
  library.
- **`Public` search generators** — `search_tracks`, `search_artists`,
  `search_albums`, `search_playlists`, `search_podcasts` all return
  `AsyncGenerator[Sequence[T]]` and paginate automatically.
- **Typed data wrappers** — `Track`, `Artist`, `Album`, `Playlist`, `Podcast`
  are fully typed `@dataclass(slots=True)` classes with `__repr__`.
- **Shared visual types** — `_common.py` extracts the repeated color/theme
  structs that Spotify returns on every entity, eliminating ~300 lines of
  duplication across the data wrapper modules.
- **`from_dict` deserializer** — recursive, camelCase-aware dataclass factory
  with `lru_cache`-backed annotation resolution.
- **`ObjectDict`** — attribute-access `dict` subclass for ergonomic raw JSON
  traversal, with optional thread-safe write locking.
- **`Pool[T]`** — generic async object pool with factory, pre-warm, capped
  eviction, and teardown callbacks.
- **`EventDispatcher`** — async event system used by `WebSocketClient`.
- **`WebSocketClient`** — async WebSocket wrapper with heartbeat manager,
  `@event` decorator, and `asynccontextmanager`-based connection lifecycle.
- **`HTTPClient`** — `wreq`-backed HTTP client with:
  - Exponential backoff + jitter retry strategy.
  - Randomised browser profile emulation (Chrome, Edge, Firefox, Opera).
  - Randomised OS emulation (Windows 30×, macOS 6×, Linux 2×).
  - Shared `ClientPool` for connection reuse.
- **`BundleSession`** — parses Spotify's HTML to extract JS bundle URLs,
  fetches and caches them, and derives persisted query hashes.
- **`AuthSession`** — TOTP-based access token + client token acquisition with
  a background auto-refresh task. No CAPTCHA solver required.
- **`timed_cache`** — TTL-aware async/sync cache decorator used for the
  expensive bundle-fetch step.
- **Five loggers**: `LoggerColour`, `StandardLogger`, `NoopLogger`,
  `InbuiltLogger`, `JsonLogger`, and `MultiLogger` fan-out — all implementing
  `LoggerProtocol`.
- **`py.typed` marker** — signals full PEP 561 type-checker support.
- `pyproject.toml` replaces `setup.py`.

### Fixed

- `types/__init__.py` had duplicate star imports causing symbols to be
  registered twice; replaced with explicit named imports.
- `utils/__init__.py` used a broken double-import pattern that shadowed the
  module-level `__all__`; replaced with explicit named imports.
- `Pool.put()` called the deprecated `asyncio.get_event_loop()` (deprecated
  in Python 3.11); replaced with `asyncio.get_running_loop()`.
- `_BaseLogger.log()` acquired the threading lock then returned early without
  releasing it when `is_enabled()` was `False`; replaced the manual
  acquire/release with a `with` statement via `contextlib.nullcontext`.
- `totp.py` had an unreachable `return FALLBACK` statement after a
  `raise RuntimeError`; removed the dead code.
- Data wrappers (`track.py`, `artist.py`, `album.py`, `playlist.py`,
  `podcast.py`) each redefined identical color/theme dataclasses; extracted
  to `_common.py` and imported from there.

### Changed

- Package layout reorganised into `connection/`, `datastruct/`,
  `specialized/`, `types/`, `utils/` sub-packages.
- `setup.py` replaced by `pyproject.toml` (Hatchling build backend).
- Minimum Python version raised from 3.11 to **3.11**.

### Removed

- `annotations.py` runtime type-enforcement decorator (`@enforce_types`,
  `@enforce`) — moved to a dev-only tool; it has no callers in v2 and
  imposes overhead on every method call.
- `parse_json_string` from `utils/strings.py` — v1 leftover with no callers
  in v2 (Spotify's `correlationId` is now parsed via the `appServerConfig`
  base64 blob).
- `setup.py`, `requirements.txt` — superseded by `pyproject.toml`.

---

## [1.2.8] — 2026-06-14 *(latest stable)*

> See the [main branch](https://github.com/Aran404/SpotAPI/tree/main) for the
> v1 changelog.