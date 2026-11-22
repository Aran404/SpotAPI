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
python -m pip install -e ".[dev,demo,connect]"
python -m pip install -r requirements-docs.txt
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
python -m spotapi connect --help
```

The [CI workflows](https://github.com/Aran404/SpotAPI/tree/main/.github/workflows)
exercise offline contracts across Python 3.11-3.13 and supported desktop OSes,
plus wheel installation checks and frontend browser tests.

**Publishing preflight:** The [release workflow](https://github.com/Aran404/SpotAPI/actions/workflows/publish.yml)
also runs its **exact tagged-release build and test steps** on every pull request and
every push to `main`. This matters because `build` and `twine` introduce dependencies
that the ordinary development test environment might not have. It builds and checks
the distributions, installs the wheel, and smoke-tests it outside the checkout.
The PyPI upload job is **skipped** unless the event is a matching `v*` tag push.

Before tagging, verify a **successful release preflight on the exact `main` commit**
you plan to tag, not just the separate cross-platform checks. You can also run the
release workflow manually for a non-publishing preflight. After pushing the tag,
verify that the tagged run's **publish** job succeeds and that the new version
actually appears on [PyPI](https://pypi.org/project/spotapi/). A GitHub release
entry is not proof that PyPI was updated.

## Live checks

Most tests run without a Spotify account or a network connection. The opt-in
live suite is different: it requires Spotify to respond, and authenticated
checks require credentials supplied only in your own environment.

```sh
python -m pytest --live=read -m "live and not authenticated" -vv
```

The scheduled public checks exercise Spotify's actual read-only endpoints.
They do **not** run on ordinary pull requests and can still miss changes to
uncovered endpoints. A manually dispatched authenticated check requires a
configured `SPOTIFY_CANARY_COOKIE` secret; missing credentials cause that check
to fail explicitly, rather than report a misleading success.

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

For current verification, check the [GitHub Actions runs](https://github.com/Aran404/SpotAPI/actions)
for the exact commit you intend to release. Historical test claims are not a
substitute for current CI results or fresh live checks.
