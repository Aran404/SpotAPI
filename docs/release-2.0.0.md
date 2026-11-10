# SpotAPI 2.0.0 release candidate

The async API lives under `spotapi`. The synchronous release is available on
PyPI as `spotapi==1.2.8`.

## What ships

Typed async catalogue access, the `spotapi search` and `spotapi get` commands,
managed cookie sessions through `Private`, playlist occurrence editing,
existing-player controls and events, entitled lyrics, and optional Studio and
terminal examples. The core keeps one runtime dependency. See the
[changelog](../CHANGELOG.md) and [migration guide](../MIGRATION.md) for the
public API and compatibility changes.

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

- Python 3.11, 3.12 and 3.13: **291 offline tests passed** on each. On Python
  3.12, the offline suite covered 74% of the package with branch coverage enabled.
  Browser checks ran against isolated local fixtures.
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

Signup/password login, creator/family/billing features, audio rendering and
automated browser challenges are outside the current API. Canvas availability and
live video switching remain unverified. Some account, password, and social writes
have offline or source coverage only. See [account boundaries](account.md),
[player coverage](player-coverage.md) and [Studio setup](studio.md).
