# Changelog

## 2.1.3 - Pending release

- Return an actionable SPOTIFY_COOKIE fallback when the optional Python keyring
  package is installed but the operating system has no secure keyring backend.
- Make the missing-session CLI regression independent of the CI runner's
  installed optional packages; verify the headless-backend failure explicitly.
- Keep the v2.1.2 GitHub tag as a historical failed publishing attempt. Its
  tagged workflow failed before uploading to PyPI; v2.1.3 supersedes it.

## 2.1.2 - 2026-11-22 (GitHub tag; PyPI publication blocked)

- Reuse saved Connect profiles in authenticated CLI commands, with explicit profile
  selection and actionable errors when credentials are missing (#100).
- Keep the Connect playback listener available if catalogue startup fails; bound
  concurrent Studio catalogue reads and clean them up during account switches.
- Report playlist/query pagination truncation instead of silently returning
  incomplete results; correct Studio's installed-version identification.
- Put the Python API before the terminal demo in English, Portuguese, Spanish,
  French and Japanese READMEs; add a public search guide with copyable examples (#103).
- Add a dated, qualified GitHub traffic snapshot for prospective sponsors and
  direct PayPal funding for voluntary support (#101, #102, #103).
- Update GitHub Actions to Node 24-compatible versions (#102).

## 2.1.1 - 2026-11-21

- Add the installable `connect` optional extra and verify its installed wheel
  on Linux, Windows and macOS; clarify browser sign-in requirements (#94).
- Add a bounded, streaming, offline-tested public playlist CSV auditor (#95).
- Improve the README's first Python example and make the Studio screenshot
  lightweight; retain the lyrics animation as an optional link.
- Fix outdated quickstart/release documentation and avoid duplicate CI runs
  when a feature branch has an open pull request.

- Add `Player.current_track_details()` for explicit current-track metadata.
- Reconnect after transient grouped cleanup failures and report `disconnect`
  on broken dealer connections.
- Raise `LoginExpired` for missing or rejected Spotify cookie sessions.
- Emit `library_change` for server collection notifications, including changes
  from other clients, with local/server echoes deduplicated.
- Add opt-in MCP playback and like tools through `--allow-player`.
- Preserve authentication failures when cleanup also fails, and keep permanent
  connection failures visible alongside transient cleanup errors.
- Prevent late like confirmations from overriding newer collection events.
- Expose public search locale selection through CLI `--language` (#88).

- Send Connect commands from the registered controller to the selected player.
  This fixes accepted commands that left playback unchanged and then timed out
  when the active player was also used as the command source (#91).

## 2.1.0 - 2026-11-13

Engineering notes: [I wrote a Python library at 16. Here are 5 things I'd fix
in the async rewrite](https://dev.to/aran404/i-wrote-a-python-library-at-16-here-are-5-things-id-fix-in-the-async-rewrite-4p62).

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
- Report the installed distribution with `spotapi --version` so executable and
  package mismatches are immediately visible.
- Require `wreq` 0.12.3 or newer within the compatible 0.12 release line for
  corrected coroutine cancellation; 0.13 remains excluded because it changes
  binary response types.

### Fixed

- Replace the migration page's intermediate-branch internals with verified
  `spotapi==1.2.8` examples, feature differences and removed-workflow boundaries.
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
