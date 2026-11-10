# Migrating to the v2 beta

v2 requires Python 3.11+ and uses `async`/`await`. Sync v1 functionality is not
implicitly available through the v2 package. Cookie-authenticated player controls
and provider-neutral CAPTCHA integration are available in v2. Pin `spotapi<2`
if you still depend on v1-only password login, family management, or session savers;
that pin does not establish whether those unofficial endpoints still work.

| Old | New | Reason |
|---|---|---|
| `QueryWrapper` / `spotapi.v2.query_wrapper` | `Queries` / `spotapi.v2.queries` (old module removed) | Name the persisted-query responsibility directly |
| Deep `specialized.data_wrappers` application imports | `from spotapi.models import ...` (old imports still work) | Discoverable public model namespace |
| Extended searches return raw dictionaries through separate operations | Typed Audiobook/Episode/User/Author/Genre results from one `searchDesktop` request | Working anonymous search with stable return types |
| `Public.get(playlist_url)` returns raw data | `PlaylistDetails`; use `Queries` for raw operations | Metadata is typed; track occurrence pagination is explicit |
| `Public.get_podcast()` returns raw metadata | `PodcastDetails`; audiobooks use `get_audiobook()` | Respect Spotify's distinct podcast/audiobook entity types |
| `Public.get(show_url)` assumes a podcast | Detects Podcast or Audiobook from response typename | Audiobooks also use Spotify show URLs |
| PlaylistTrack requires presentation fields | Identity required; duration/artwork/ratings may be None | Legitimate partial Spotify payloads remain usable |
| Playlist attributes are opaque dictionaries | Typed key/value attributes | Standard dataclass JSON export stays plain and predictable |
| Query-cache format 1 | Format 2, rebuilt once | Discard incomplete hashes produced by the former JS/CSS chunk-map mix-up |
| v1 `Song().paginate_songs(...)` | `Public.search_tracks(...)` with `async for` | Async I/O and typed results |
| Nested raw search dictionaries | `result.tracks`, `track.name`, `artist.name` | Discoverable result models |
| Deep v2 imports | `from spotapi import Public, SpotAPIError` | Small explicit root exports; existing `spotapi.v2` imports remain |
| Public operations rely on an implicit loop pool | `Public` owns each operation; `async with Catalogue()` reuses a client | Deterministic cleanup and explicit connection reuse |
| `query_client_pool()` returns generic `Pool` | Shared owner with `acquire()`, `close()`, `closed` | Preserve borrowing/shutdown interface; generic-pool internals are no longer available |
| Global `connection.ClientPool` | `async with HTTPClient()` or `AsyncClient()` | Remove an unused, globally loop-bound pool above wreq's pool |
| Unknown POST/PUT/PATCH/DELETE replayed by default | One attempt by default | Ambiguous failures may already have applied mutations |
| Raw read-only POST inherits retries | Set `retry_safe=True` or explicit `max_attempts` | Make replay safety deliberate; built-in catalogue reads opt in automatically |
| Unknown Pathfinder operation inherits retries | One attempt unless explicit `max_attempts` is supplied | Operation names alone do not prove read semantics |
| Permanent HTTP wreq exceptions escape | `HTTPError` with original exception as cause | One library base (`SpotAPIError`); programmer errors and cancellation still propagate |
| WebSocket listeners continue after context exit | Pending listeners are cancelled and awaited | Connection-scoped ownership |
| Unlimited pending event callback tasks | 256 by default, configurable on `EventDispatcher(max_pending=...)` | Bound slow-listener memory; saturation is logged |
| Indefinitely old query-cache entries accepted | Build-bound cache, 24-hour expiry, validated hashes, bounded input | Stale or malformed caches become misses |
| `QueryCache.load()` / `save(hashes)` with a bare JSON mapping | Optional build version on load/save; versioned envelope on disk | Existing files are refreshed once; matching builds skip chunk downloads |
| `BundleSession.warm()` retains every JavaScript chunk | Retains the main bundle after extracting hashes; `load()` explicitly fetches all sources | Avoid retaining source no longer needed for requests or token renewal |
| `pytest` silently makes live requests | Use `pytest --live=read` explicitly | Reproducible offline contributor workflow |
| pyproject permits wreq upgrades while requirements pins 0.12.0 | Both pin 0.12.0 | Test and install the same transport version |
| Legacy `setup.py` with v1 metadata | Hatch / `pyproject.toml` only | Remove competing version and dependency metadata |

`ObjectDict` mapping keys remain original JSON keys. `data["items"]` and
`data._items` refer to the same key. When both `items` and `_items` exist,
use `data["_items"]` or `data.__items` for the latter. Methods such as
`items()` and `get()` retain normal dictionary meaning. Historical callers
with pre-escaped `_items` pages remain accepted by page parsers.

Search metadata is legitimately optional. Check `track.duration is not None`
before reading milliseconds, and check optional artist/publisher/artwork
objects before dereferencing them. `Public.get_track` returns `TrackDetails`;
`Public.get(url)` returns a union based on the resource identified by the URL.

Use `Public` for one-shot work. Lookups close before returning; page streams
close on exhaustion or `aclose()`. Wrap streams in `contextlib.aclosing` if
you may break early. Reuse `async with Catalogue() as spotify` for multiple
operations, proxy configuration, and raw queries through `spotify.queries`.
A catalogue cannot be reopened after closing. Injected `Queries` remain
owned by their caller. `close_query_clients()` only applies to lower-level
code using the implicit `Queries()` pool.

Authenticated playlist operations live in `spotapi.v2.playlist` and accept an
authorized `AuthSession`. They deliberately use one attempt. Reconcile state
after ambiguous failures before deciding whether to retry yourself. The
low-level WebSocket API retains wreq's error types.


Player helpers now accept `AsyncClient.from_cookies(...)` clients (or an
explicit `AuthSession`). `PlayerStatus` is a scoped dealer observer, and
`Player` adds device selection and single-attempt control. Replace v1's
threaded `EventManager.subscribe` with async `@player.event` or
`@player.listen("track_change")` callbacks inside `player.connect()`.
Property reads use cached typed snapshots; `refresh()` performs an explicit
request. Volume is an integer percentage from 0 to 100. HOBS observer IDs and
full playback device IDs are separate arguments. See [the player guide](docs/player.md).

`await player.start()` manages reconnection and stops with `await player.close()`.
Use `wait_for(event, check=..., timeout=...)` for matching events. Connection
cleanup includes the owned control-only registration, observers, timers and
callbacks; the caller still owns the supplied authenticated client.

Queue edits preserve occurrence UIDs and use the last observed revision.
Library and history access are also reusable as `LikedTracks(client)` and
`ListeningHistory(client)`. Recents represent dated grouped contexts and saved
actions; they do not provide exact per-play timestamps.
