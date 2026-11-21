# SpotAPI Connect

`spotapi connect` is an interactive terminal controller for **existing Spotify
players**. It does not download, decode or stream audio. It is built from the
same typed `Player` and `Catalogue` objects available to Python applications.

## Install

From a checkout:

```bash
python -m pip install -e ".[connect]"
```

From a published version containing Connect:

```bash
python -m pip install "spotapi[connect]"
```

The `connect` extra installs the terminal UI and OS-keyring support for saved profiles.
Browser sign-in is a separate optional installation, described below.

Browser sign-in is optional. Only if you want Connect to open a fresh login
window (including with `--force`), install the browser extra and its Chromium
runtime:

```bash
python -m pip install "spotapi[browser]"
python -m playwright install chromium
```

With an existing `SPOTIFY_COOKIE` environment variable or a saved keyring
profile, neither Playwright nor its browser installation is required.

## Sign in and choose an account

```bash
spotapi connect
spotapi connect --profile personal
spotapi connect --profile work --force
```

If `SPOTIFY_COOKIE` is set in the environment, the default profile uses that
value, without storing it. Otherwise, Connect attempts to reopen the named
session from the **OS credential store**. If none exists, Connect attempts to open Spotify's normal login in an
isolated Chromium window. For that first-time flow, install the optional
`browser` extra as above; otherwise supply `SPOTIFY_COOKIE` yourself.

`--force` **always opens a fresh login window**, ignoring the saved session and
shell cookie. After Spotify authorizes the session, only its `sp_dc` cookie is
saved under that profile name in your operating system's keyring. A failed or
cancelled login does not overwrite a stored profile. Profile names are selected
at launch; the terminal does not silently switch accounts while connected.

The keyring is deliberate: Connect never creates or modifies a plaintext
`.env` file. If you prefer `.env`, load `SPOTIFY_COOKIE` into the process
*explicitly* before launching Connect. Never commit credentials to Git.

The browser login uses a lazy Playwright import. On a system without Playwright
or Chromium, existing shell cookies and saved keyring profiles still work.

## Controls

Type any of these commands into the one input at the bottom of Connect.
Leading slashes are optional.

| Command | Action |
|---|---|
| `/devices` | Inspect existing Spotify devices and their numbers |
| `/use 2` | Target device 2 **without** transferring playback |
| `/transfer 2` | Ask Spotify to transfer playback to device 2 |
| `next`, `previous` | Skip a track on the selected player |
| `pause`, `resume`, `toggle` | Control playback |
| `seek 1:30` | Seek to a position; accepts `seconds`, `mm:ss`, `hh:mm:ss` |
| `volume 60` | Set device volume in percent |
| `shuffle on` | Enable shuffle where Spotify allows it |
| `repeat track` | Set repeat mode (`off`, `context`, `track`) |
| `search Daft Punk` | Show up to five tracks |
| `queue 1`, `play 1` | Use the last search result number |
| `queue spotify:track:...` | Queue an explicit track URI |
| `refresh` | Request a fresh Connect snapshot |
| `quit` | Close the controller and its connection |

**Keys:** `Ctrl+P` opens Textual's command palette, `Ctrl+D` lists devices,
`Ctrl+L` focuses input, and `Ctrl+Q` quits.

Device IDs, song names and the up-next list come from Spotify state updates.
The progress bar uses the library's projected local playback position; it is
not a claim of packet-level continuous synchronization.

## Engineering and verification

The terminal starts one `Player.start()` supervisor and lets it reconnect on
transient failures. A separate authenticated `Catalogue` performs searches.
Both borrow the same client, which is closed only after the UI exits. Command
errors are visible in the log. Commands are **not automatically retried** after
an ambiguous timeout; the player may have already applied an operation.

`Player.select()` only changes the target for future commands;
`Player.transfer()` requests an actual transfer. The UI never shows a different
active device's now-playing state as though it belonged to your selected one.

This uses undocumented Spotify web-player behavior, which can change without
notice. Not every player and account supports every control. An acknowledgement
does not by itself prove that the player produced audio; verify the actual
Spotify device when recording a demonstration.

### If `spotapi connect` is an invalid command

The `spotapi` executable may still belong to an older installed release even
when your source checkout has `spotapi/_connect/`. From the **root of your
current checkout** on Windows, run:

```powershell
python -m pip install -e ".[connect]"
python -m spotapi --help
python -m spotapi connect
```

`python -m spotapi` uses the `spotapi` imported by that interpreter, avoiding
confusion with an old `spotapi.exe` launcher on the PATH. To inspect both:

```powershell
where.exe spotapi
python -c "import spotapi, spotapi.cli; print(spotapi.__file__); print(spotapi.cli.__file__)"
```

If they disagree, remove the obsolete installation or correct your PATH; do
not overwrite library files individually to repair a launcher mismatch.

The terminal controller needs `spotapi[connect]`, but **does not need
Playwright** when `SPOTIFY_COOKIE` or a saved account is available. Fresh
browser sign-in (`--force`) additionally needs `spotapi[browser]` and
`python -m playwright install chromium`.

## Interactive terminal UI

Connect presents a compact playback card, an authenticated profile label, the
selected playback device, contextual search/device/queue details, and a single
shell-like command composer (`spotapi@profile ❯`). You can use the terminal
**with the mouse or keyboard**:

- Type `/` or press `Ctrl+K` for a command list with short descriptions.
- Use `↑` / `↓` in the suggestions, then `Enter` to select; `Tab` completes.
  Selecting a suggestion fills the composer—it does **not** automatically run a
  potentially mutating command. Submit the completed command to execute it.
- Click **Prev**, **Pause/Resume**, **Next**, or **Devices**, or use `Tab` to
  navigate the visible controls without the mouse.
- Click **Activity** or **Logs**, or press `F2` to switch channels. Reconnect
  retries are summarized in Activity and counted in the separate Logs channel;
  raw authentication exceptions and credentials are never displayed.
- `Ctrl+L` focuses the composer; `Ctrl+Q` exits. The layout adapts to narrower
  and shorter terminal windows, including embedded terminals in VS Code.

The queue panel shows **only entries in Spotify's observed `next_tracks` state**.
Its first entries are enriched with catalogue titles/artists when the snapshot
omits them. If Spotify reports only one upcoming item, Connect cannot honestly
promise the remaining album/playlist order—especially under shuffle. It does
not invent placeholder entries or silently fill the list with album tracks.
`refresh` requests a new Connect snapshot, but Spotify may still provide an
incomplete upcoming queue. This is a backend observation limitation, not a
claim that the actual Spotify player has only one upcoming track.
