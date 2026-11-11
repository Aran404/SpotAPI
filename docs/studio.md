# SpotAPI Studio

From the v2 checkout:

```bash
python -m pip install -e ".[studio]"
python -m examples.studio
```

Studio uses the platform's native WebView through pywebview, with no bundled browser
or remote frontend dependencies. Windows needs the Microsoft Edge WebView2 runtime.
Other platforms need a supported pywebview engine; see its
[installation guide](https://pywebview.flowrl.com/guide/installation.html).

## Sign in

Public discovery works immediately. For account features, choose **Connect Spotify**
and sign in yourself in the separate Spotify window. Studio reads only that window's
`sp_dc` after Spotify returns to its web player, then validates the session through
`AsyncClient.from_cookies`. It does not inspect an existing browser's profile.

Alternatively, set `SPOTIFY_COOKIE` in the environment or the root `.env`. The
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

## What this example tests

Browser tests exercise bundled assets, navigation, detail views, mutation
cancellation and compact layouts with an isolated local bridge. Native-window
checks and real backend reads are separate evidence; mocked browser tests do not
prove Spotify endpoint behavior. User-driven login has a tested cookie-import
contract, not an automated end-to-end login claim.

```bash
python -m pip install -e ".[dev,demo,studio]"
python -m playwright install chromium
python -m pytest -q
python -m pytest --live=read -q
python -m pytest --live=all -q
```

The final command also permits playback changes and temporary-playlist mutations.
Run it only against your own prepared account. Ordinary tests are offline.
Missing cookies skip authenticated integration checks; missing browser binaries
skip browser UI tests with an installation hint.

Studio is a Spotify workbench example, not complete Spotify client parity. Account
signup, billing, family enrollment, audio rendering, and automatic browser-challenge
completion are outside its implemented scope. Advanced renderer registration and
transport primitives remain available programmatically in the library.
