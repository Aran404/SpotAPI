---
description: How SpotAPI validates releases and what each class of test proves.
---

# Release quality and verification

SpotAPI validates a release in three layers: **offline contracts**, **installed
artifacts**, and **optional live checks**. Passing one layer does not imply the
others passed. This is the process used to make changes without accidentally
breaking applications.

## Before publishing

From a checkout with the development extras installed:

```sh
python -m pip install -e ".[dev,demo]"
python -m pytest -m "not live" -q
python -m pyright
python -m ruff check .
python -m black --check .
python -m mkdocs build --strict
```

Build the wheel/source distribution and install the wheel in a **clean environment
outside the source tree**. Check the commands below against the installed package,
not an editable import:

```sh
python -m spotapi --version
python -m spotapi search --help
python -m spotapi discover --help
python -m spotapi studio --help
```

The [CI workflows](https://github.com/Aran404/SpotAPI/tree/main/.github/workflows)
exercise offline contracts across Python 3.11-3.13 and supported desktop OSes,
plus wheel installation checks and frontend browser tests.

## Live checks

Most tests run without a Spotify account or a network connection. The opt-in
live suite is different: it requires Spotify to respond, and authenticated
checks require credentials supplied only in your own environment.

```sh
python -m pytest --live=read -m "live and not authenticated" -vv
```

Playback-changing tests are **not** part of scheduled public CI. To verify
controls on your own device, see the procedure in [Player controls](player.md).
Those tests may temporarily change your active playback and should be run only
when you intend to exercise those operations.

## What passing tests means

| Evidence | What it establishes | What it doesn't |
|---|---|---|
| Offline unit tests | Expected parsing, lifecycle, errors and request contracts for captured cases | That Spotify still accepts live requests |
| Installed-wheel smoke test | Packaging, imports and command availability on tested machines | That optional GUI engines run on every host |
| Browser UI tests | Deterministic interaction with the bundled Studio frontend | Live authentication or playback |
| Read-only live tests | Current response compatibility for the exercised operations | Unexercised endpoints or write operations |
| Playback live tests | Device-specific behavior for the exercised actions | Universal Free/Premium or device compatibility |

## Boundaries

SpotAPI uses unofficial web-player interfaces that Spotify can change. A
successful HTTP response or Connect acknowledgement is not necessarily proof
that a remote player changed state; tests check fresh playback state where
possible. Some player devices and account entitlements may reject actions.
See [player capability boundaries](player-coverage.md), the
[request policy](transport.md), and [troubleshooting](troubleshooting.md).

The dated results from the November 13, 2026 hardening run are preserved in the
[maintainer verification snapshot](https://github.com/Aran404/SpotAPI/blob/main/docs/development/release-verification-2026-11-13.md).
They are historical observations, not the current release status or a substitute
for the CI result on a new commit.
