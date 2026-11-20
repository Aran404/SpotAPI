---
description: Fix SpotAPI installation, command, account and player problems.
---

# Troubleshooting

Start with the error you actually see. Public search does not require a Spotify
account. Account and player operations do.

## `spotapi` is not recognized

Install and launch with the **same** Python interpreter:

```sh
python -m pip install -U spotapi
python -m spotapi --version
python -m spotapi search "Daft Punk"
```

On Windows, replace `python` with `py` if you used the Python launcher. In a
virtual environment, activate it before installing and running the command.
If the version is unexpected, check `python -m pip show spotapi`.

## Discover or Studio asks for an extra

The base installation intentionally does not install graphical or terminal UI
dependencies. Install only the interface you plan to use:

```sh
python -m pip install "spotapi[demo]"
python -m spotapi discover "Daft Punk"
```

```sh
python -m pip install "spotapi[studio]"
python -m spotapi studio
```

Windows Studio needs the Edge WebView2 runtime; other operating systems need a
supported [pywebview backend](https://pywebview.flowrl.com/guide/installation.html).
A headless server is not a supported desktop Studio environment.

## Search takes a long time the first time

The first public operation discovers Spotify's current web-player query IDs.
Results are cached for that Spotify build. Some rarely used operations need
additional discovery, so a warm search does not guarantee every other request
will be fast. Reuse one `Catalogue` scope for multiple calls. Avoid repeatedly
creating one-shot clients in a tight loop.

## `Set SPOTIFY_COOKIE` or sign-in fails

Only account features need an authenticated session. Studio can open Spotify's
normal login window; scripts can supply `SPOTIFY_COOKIE` as described in
[Studio sign-in](studio.md#sign-in). Treat the `sp_dc` cookie like a password;
never paste it into issues, logs, screenshots or public code. Cookies can expire
or be revoked. Reauthenticate rather than repeatedly retrying an expired session.

## No active playback device

Player controls operate an **existing** Spotify player: open Spotify on a
compatible device and start playback there, then run `spotapi player status`.
Check that you are authenticated to the same account. SpotAPI does not create
audio playback, decode protected tracks or turn speakers into Spotify Connect
renderers. Device and account capabilities vary.

If a control times out, inspect the fresh playback state before retrying: the
server may have accepted the command without the device applying it. Avoid
blindly repeating queue changes or other non-idempotent actions.

## Still stuck?

Capture the SpotAPI version, Python version, operating system, exact command,
**sanitized** error text and expected behavior. For player problems, include
whether the device appeared in `player status` and whether its state changed.
Do not include cookies, tokens, raw authenticated HTTP headers or private
account data. Open a [bug report](https://github.com/Aran404/SpotAPI/issues/new/choose)
with a minimal reproduction.
