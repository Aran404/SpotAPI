# 2.0.0b3 release candidate

Prepared on 2026-11-10; not yet pushed, tagged or published. PyPI already contains
`2.0.0b1` and `2.0.0b2`, so this candidate uses the next beta version.

## What ships

Typed async catalogue access, cookie-authenticated account/library helpers,
playlist metadata and exact-occurrence editing, existing-player controls and
events, entitled lyrics, and optional Studio/terminal examples. The core keeps
one runtime dependency. See the [changelog](../CHANGELOG.md) and
[migration guide](../MIGRATION.md) for the public API and compatibility changes.

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

- Python 3.11, 3.12 and 3.13: **288 offline tests passed** on each, with 25 opt-in live checks
  skipped in ordinary runs. Browser checks ran against isolated local fixtures.
- Full opt-in live suite on Python 3.12: **24 passed, 1 skipped**. This includes
  authenticated account, library, lyrics and Studio reads; temporary-playlist
  metadata/UID editing and pin/unpin; and track save/remove with original unsaved
  state restored. Temporary playlists were removed from the library.
- Playback mutation check skipped because Spotify reported no active device/track.
  That skip is not a pass. Current command changes have offline dealer-packet tests
  and live observer coverage, not a new successful playback mutation run.
- Strict Pyright, Ruff, Black and whitespace checks passed. The wheel and source
  archive built and passed Twine metadata checks. A fresh virtual environment
  imported the installed `2.0.0b3` wheel outside the checkout. Both artifacts were
  scanned for credential literals, `.env` and local commercial planning/captures;
  none were included.

Python 3.11's optional terminal image dependency emits a Pillow deprecation warning;
Pillow remains bounded below version 14. No warning was suppressed. Python 3.13
was verified in a fresh environment with current optional development/demo
dependencies. Hosted GitHub Actions jobs remain pending until the branch is pushed.

## Boundaries

This is a public beta, not complete Spotify or v1 parity. Signup/password login,
creator/family/billing features, audio rendering and automated browser challenges
are not implemented. Canvas availability and live video switching remain
unverified. Account/password/social writes have varying source/contract evidence;
they are not all live-tested. See [account boundaries](account.md),
[player coverage](player-coverage.md) and [Studio setup](studio.md).
