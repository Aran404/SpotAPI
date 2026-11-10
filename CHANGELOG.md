# Changelog

## 2.0.0b3 — unreleased

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

This is a beta rewrite, not complete Spotify or v1 parity. See the
[release checks](docs/release-2.0.0b3.md) and [player coverage](docs/player-coverage.md).

## v1 history

See the [repository history](https://github.com/Aran404/SpotAPI/commits/main/)
for changes predating the rewrite.
