# Changelog

## 2.1.0 - 2026-11-13

### Added

- Launch the packaged desktop application with `spotapi studio` after installing
  `spotapi[studio]`; its frontend and icons ship in the wheel.
- Keep first results and sign-in visible in Studio's minimum-size window,
  with independently scrollable navigation.
- Launch the packaged terminal browser with `spotapi discover` and the demo extra.
- Read artist Discovered On playlists, concerts, similar albums and image palettes.
- Read typed podcast captions, explicit embed snapshots and public media assets.
- Export JSON-safe models, collect ordered partial-failure batches, optionally
  cache anonymous responses and reuse the async core from `SyncCatalogue`.
- Optional browser login, OS-keyring sessions and read-only MCP integration.
- Read the Docs configuration, generated API reference and a Spotipy migration guide.

### Changed

- Discover the main and search-route bundles first, loading other routes on demand
  with eight continuously scheduled workers and build-specific hash caching.
- Managed account scopes accept explicit proxy and language options.
- Keep sponsorship placements below usage material, with optional integration
  partnerships and privately quoted scope.
- Require `wreq` 0.12.3 or newer within the compatible 0.12 release line for
  corrected coroutine cancellation; 0.13 remains excluded because it changes
  binary response types.

### Fixed

- Dealer disconnects wake command waiters and clear readiness; temporary device
  loss no longer discards a valid late ACK. Quiet dealers allow one snapshot
  refresh within the existing deadline; old snapshots cannot prove success.
- Playback restoration preserves its original target and primary error, and
  does not confirm a seek that failed. Commands are never silently replayed.
- Failed route downloads can be retried rather than becoming permanent misses.
- Anonymous embed fallback preserves proxies and cannot downgrade borrowed scopes.
- Sync shutdown rejects nested event loops before losing resource ownership.
- Discover releases cached images when feed shutdown fails, and Escape/Down
  return keyboard focus from search to results.

## 2.0.0

- Use `spotapi` for all async imports. The synchronous release remains available as `spotapi==1.2.8`.
- Install the `spotapi` command for anonymous track search and JSON resource lookups.
- Open a managed account session with `Private.from_cookies()`.
- Follow, unfollow and check artists by ID, URI or URL through `account.library`.
- Fetch multiple tracks, albums or artists through one catalogue client.
- Move exact playlist occurrences by UID, including duplicate tracks.
- Set or clear a custom JPEG playlist cover.
- Stream typed audiobook chapter pages for available titles.
- Browse Studio lyrics through LRCLIB and seek from timed lines on the matching track.

### Added

- Typed async catalogue search, lookups, credits, discovery and lazy pagination.
- `Public` for self-cleaning one-shot calls and `Catalogue` for connection reuse.
- Cookie-authenticated account, library, rankings, profiles and notifications.
- Existing-player controls, async listeners, occurrence-aware queue editing,
  sleep timers and entitled lyrics.
- Playlist metadata editing and removal by exact occurrence UID.
- A provider-neutral async CAPTCHA protocol for explicit account operations.
- Optional Studio and terminal examples; their dependencies stay outside the core.
- Offline lifecycle and contract tests, opt-in live checks, and release workflows.

### Changed

- Authenticated feature requests use `authorized=True`; credential assembly,
  renewal, destination validation and redirect policy live in `AsyncClient`.
- Identical artwork color and contrast-role shapes share `RGBA` and
  `ContrastPalette` value types instead of nine duplicate dataclasses.
- Result types live in the `models` package, grouped by domain; importing them
  does not load the native HTTP transport. Old implementation paths were removed.
- Internal endpoint templates, protobuf, bundle parsing and TOTP helpers live
  in `_protocol`; repeated resource paths share one escaping implementation.

- Advanced searches use immutable `SearchOptions` with snake_case fields and
  `options=`; native GraphQL variable names remain internal to serialization.
- Direct transport access is `client.transport` and `client.websocket`.
- Authenticated profile attributes expose Python field names; see the migration guide.

- Python 3.11+ and async/await are required. See [migration](MIGRATION.md) for
  compatibility changes and v1 features that have not been ported.
- Hatch and `pyproject.toml` define package metadata; `requirements.txt` retains
  the same tested transport pin.
- Known reads opt into bounded retries. Mutations are not replayed after
  ambiguous failures; account CSRF rotation is handled explicitly.
- Query hashes use a build-bound disk cache. Cached startup fetches the main
  bundle rather than every chunk, and discards unneeded source after parsing.
- Clients own refresh, socket and callback tasks and release them on shutdown.
- Logging defaults to the standard library without configuring application sinks.

### Fixed

- Directly constructed authentication sessions attach to their owning client,
  so safe request renewal and shutdown behave consistently across factories.
- `max_attempts=1` also prevents a second request after an authorization failure.
- HEAD, 204 and 205 responses may be empty even with a JSON Content-Type.
- Accepted cleanup statuses use `expected_statuses`, preserving normal
  authorization handling without duplicating status checks in features.

- Thread-local implicit query owners no longer share a slotted registry across threads.
- Managed authorization rebuilds fresh credential headers after renewal; custom header names and JSON media types are case-insensitive.
- The model decoder recognizes native GraphQL `__typename` fields consistently with search preflight.
- Profile options, profile attributes and notification identities/cursors reject malformed contracts.
- Exception logging respects the configured severity filter and synchronization.

- Playlist add/remove operations reject error unions such as `NotFound` instead
  of interpreting a nonempty error object as success.
- Commands with `wait=True` require a matching dealer ACK or a fresh state proving
  the result, even when the HTTP response contains no acknowledgement ID.
- Studio cancels timed-out sign-ins, prevents concurrent cookie imports, and
  discards delayed data from the previous account.
- Library saves, pins and user follows validate Spotify's confirmation instead
  of accepting nonempty error responses or incomplete mutation results.
- Playback restrictions, canonical playlist metadata reads, and optional model
  fields are handled explicitly.

See the [release checks](docs/release-checks.md) and [player coverage](docs/player-coverage.md)
for supported workflows and known gaps.

## v1 history

See the [repository history](https://github.com/Aran404/SpotAPI/commits/main/)
for changes predating the rewrite.
