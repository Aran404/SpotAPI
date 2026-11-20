# SpotAPI Studio

Install the optional desktop application:

```bash
python -m pip install "spotapi[studio]"
spotapi studio
```

The application, frontend and icons ship in the wheel. Contributors running a
checkout can instead use `python -m pip install -e ".[studio]"`.

Studio uses the platform's native WebView through pywebview, with no bundled browser
or remote frontend dependencies. Windows needs the Microsoft Edge WebView2 runtime.
Other platforms need a supported pywebview engine; see its
[installation guide](https://pywebview.flowrl.com/guide/installation.html).

## Sign in

Public discovery works immediately. For account features, choose **Connect Spotify**
and sign in yourself in the separate Spotify window. Studio reads only that window's
`sp_dc` after Spotify returns to its web player, then validates the session through
`AsyncClient.from_cookies`. It does not inspect an existing browser's profile.

Alternatively, set `SPOTIFY_COOKIE` in the environment or `.env` in the directory you launch Studio from. The
provided session remains in Python; it is not sent to the local page, printed,
stored by Studio or returned from the bridge. The login WebView uses private mode.
Login may require Spotify's own browser challenge. Stealth and CAPTCHA bypass are
not part of this example.

For your own scripts, you can copy your session from Chrome after signing in
to `open.spotify.com`. Open DevTools, select **Application → Storage → Cookies**,
select `https://open.spotify.com`, and copy the value of `sp_dc`. Set
`SPOTIFY_COOKIE` to `sp_dc=<value>` in your shell or local `.env`. Studio reads
the file automatically. Python scripts that use `os.environ` need the variable
exported by their shell or loaded by their own configuration. Treat the cookie
like a password and keep the file out of version control.

## Explore

- **Discover:** ten search categories, direct Spotify links, typed details, credits,
  radio, recommendations, related artists and releases. Press `/` to focus search.
  Open an artist or album by selecting its name. Use **Back** in the detail view
  to retrace your path without losing the original search.
- **Your collection:** library items, liked songs, affinity rankings, recents and
  notifications. Reading notifications does not acknowledge them.
- **Player:** an existing device's queue, play/pause, skip, seek, volume, transfer,
  shuffle/repeat when permitted, and lyrics. No audio renderer is bundled.

- **Feature lab:** explicit forms for account reads/edits, playlist and folder
  mutations, exact occurrence removal, saves, pins, follows, Blend invitations,
  notification acknowledgement, queue replacement and player timers/signals.
- **Live events:** bounded summaries from real `listen` decorators, not a raw
  websocket dump. Rich typed responses remain available in expandable inspectors.

**Lyrics** looks for a matching recording on [LRCLIB](https://lrclib.net/) without
a Spotify login. The lookup sends the title, artist, album, and duration to
LRCLIB. If there's no public match, a connected Spotify account can use its
available Spotify lyrics. Select a timed line to seek when that recording is
playing on your connected device.

The page only receives the named `request` and `login` bridge methods. It cannot
invoke arbitrary Python attributes. Remote login pages receive no Python bridge.
Account changes require explicit confirmation, and password/token inputs clear
after completion. Profile/password changes can require a caller-supplied CAPTCHA
token; no solver vendor is bundled.

## Scope and verification

Studio is a desktop workbench for exploring Spotify data and controlling
existing players. It does not decode or stream full-track audio or replace
Spotify account signup, billing and subscription management.

For frontend tests, live API checks and their limitations, see
[release quality and verification](release-checks.md). Advanced player and
renderer interfaces are documented in [Player and status](player.md).
