# SpotAPI 2 release checks

The async API lives under `spotapi`. The synchronous release is available on
PyPI as `spotapi==1.2.8`.

## What ships

Typed async catalogue access, the `spotapi search` and `spotapi get` commands,
managed cookie sessions through `Private`, playlist occurrence editing,
existing-player controls and events, and optional Studio and
terminal examples. The core keeps one runtime dependency. See the
[changelog](https://github.com/Aran404/SpotAPI/blob/main/CHANGELOG.md) and [migration guide](https://github.com/Aran404/SpotAPI/blob/main/MIGRATION.md) for the
public API and compatibility changes.

Studio includes linked track, artist, and album views, typed response inspectors,
and public lyrics via LRCLIB. A connected player can seek from synchronized lines.

Release cleanup fixed mutation error payloads being mistaken for success,
incorrect event subscriptions, missing-ACK confirmation, account-switch response
races and timed-out sign-in tasks. Studio action lookup and CSS overrides were
simplified. Release CI now verifies an installed wheel rather than potentially
importing an editable checkout.

Library save/remove and pin/unpin success contracts were checked live. Their
wrappers now reject missing or failed confirmations. Follow/unfollow confirmation
uses Spotify's deployed client contract and offline tests; no social mutation was
sent to another user. Batch operations can partially apply before failure: inspect
current state before retrying. Mutations are not silently replayed.

## Verification

### Current working tree: November 13, 2026

On Windows with Python 3.12, 440 offline tests passed, with 29 live cases
deselected. Strict Pyright, Ruff and Black passed. Live anonymous search returned
tracks, artists and albums; a typed track lookup also passed. These checks used
an explicitly configured environment proxy, not a change to transport defaults.
Authenticated authorization, profile and plan reads also passed. A broader
read-only run completed six public cases but exceeded its four-minute limit;
it is not recorded as a passing full live suite.
The separate artist-discovered-on live contract also passed. Its first call
required full route discovery and took 107.5 seconds through this proxy;
uncommon operations can still have substantial cold-discovery cost.

The longer read-only run passed seven account/catalogue cases, then failed
to discover the related-artists hash in this proxied environment. A separate
live request verified the last observed hash and returned 40 typed artists;
that value is now a fallback after current-bundle discovery. Incomplete bundle
downloads no longer permanently suppress subsequent discovery attempts.

Playback regression tests cover dealer disconnects with and without ACK IDs,
late ACKs during temporary device loss, cancellation and failed-seek cleanup.
One deadline-bound snapshot read can confirm a quiet dealer's command; it
never resends the mutation and cannot use an old snapshot as proof.
The targeted live playback rerun skipped because no active music player was
available; these fixes are not recorded as live playback verification.

Cold search now loads the main and search-route bundles, discovering other
routes only when an operation needs them. One traced run made two bundle
requests and completed search in 21.3 seconds, compared with an earlier run's
168 bundle requests and 80.9 seconds. These are individual network observations,
not a latency guarantee. Regression tests cover build invalidation, shared
discovery and the eight-worker concurrency bound. Broad live verification and
hosted cross-platform CI remain release gates.

The strict MkDocs build and wheel/source builds passed. An isolated environment
using the installed wheel outside the checkout imported the package, found the
packaged terminal demo and displayed CLI help. Artifact inspection found no
`.env` credential file or internal development plans. Offline combined
statement/branch coverage is 72.3% with the packaged Studio now included in
the measurement (the earlier library-only baseline was 74.5%); this is not exhaustive
endpoint coverage.

The observations below describe earlier validation of the release candidate.
They do not certify subsequent additions in this working tree.

### Distribution and documentation review

The next development version is `2.1.0.dev0`: PyPI and Git already contain
`2.0.0`. No release was published by this review. Studio now ships as an optional
application behind `spotapi studio`, with its frontend and native icons in the
wheel. The example module remains a compatibility launcher. Browser checks cover
the minimum native window size, including visible results and reachable sign-in.
Native launch failure and normal shutdown have deterministic ownership tests.

Read the Docs uses its version-2 MkDocs configuration with pinned documentation
dependencies and strict builds. The hosted URL returned HTTP 403 from this
environment, so project activation and the hosted build are not certified here.
Confirm those in the Read the Docs dashboard. Main-branch integration still
requires the hosted platform matrix to pass; a source push is not a PyPI release.

### Earlier release-candidate observations

- Offline tests run on Python 3.11, 3.12 and 3.13. Browser checks run against
  isolated local fixtures.
- The full opt-in live suite exercises
  authenticated account, library, lyrics and Studio reads; temporary-playlist
  metadata/UID editing and pin/unpin; and track save/remove with original unsaved
  state restored. Temporary playlists were removed from the library.
- An existing player was tested live for pause, resume, queue entry add/remove,
  options, the pause timer and seek. On that device, resume repeatedly timed out
  after seeking while paused. Restoring play/pause before seeking passed the
  same scenario and verified the final playback state.
- Strict Pyright, Ruff, Black and whitespace checks passed. The wheel and source
  archive built and passed Twine metadata checks. A fresh virtual environment
  imported the installed wheel outside the checkout and ran both CLI commands
  against Spotify. Neither artifact included `.env`, local planning, exploratory
  captures, or the configured cookie.

Python 3.11's optional terminal image dependency emits a Pillow deprecation warning;
Pillow remains bounded below version 14. No warning was suppressed. Python 3.13
was verified in a fresh environment with current optional development/demo
dependencies. Hosted GitHub Actions jobs remain pending until the branch is pushed.

## Boundaries

Jam, signup/password login, creator/family/billing features, audio rendering and
automated browser challenges are outside the current API. Canvas availability and
live video switching remain unverified. Some account, password, and social writes
have offline or source coverage only. See [account boundaries](account.md),
[player coverage](player-coverage.md) and [Studio setup](studio.md).
