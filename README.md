<p align="center">
  <img src="assets/spotapi-icon.svg" width="112" alt="SpotAPI logo">
</p>

<h1 align="center">SpotAPI</h1>

<p align="center">
  <strong>Build Spotify apps in Python with a typed, async API.</strong>
</p>

<p align="center">
  Use SpotAPI for Spotify's public catalogue, playlists and connected players.<br>
  <strong>No developer app or API key for public data.</strong>
</p>

<p align="center">
  <a href="#get-started">Get started</a> ·
  <a href="#explore-in-the-terminal">Explore</a> ·
  <a href="#build-with-python">Python API</a> ·
  <a href="https://spotapi.readthedocs.io/">Documentation</a> ·
  <a href="SPONSORSHIP.md">Sponsor</a>
</p>

<p align="center">
  <a href="https://discord.gg/vcFvvTuQzn"><img src="https://img.shields.io/badge/Discord-Join_The_Open_Odyssey-5865F2?style=for-the-badge&amp;logo=discord&amp;logoColor=white" alt="Join The Open Odyssey community on Discord"></a>
</p>

<p align="center">
  <strong>Language:</strong> English · <a href="README.pt-BR.md">Português (Brasil)</a> · <a href="README.es.md">Español</a> · <a href="README.fr.md">Français</a> · <a href="README.ja.md">日本語</a>
</p>

## Get started

Python 3.11+ is required. Start with a real search—no Spotify login, Client ID or configuration needed.

```bash
python -m pip install spotapi
python -m spotapi search "Daft Punk"
```

Use the same API in Python:

```python
import asyncio
from spotapi import Public

async def main():
    results = await Public.search("Daft Punk", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)

asyncio.run(main())
```

[More Python examples](#build-with-python) · [Playlist audit and CSV export](examples/playlist_audit.py) · [No-API-key Python guide](docs/no-api-key.md)

The first request may be slower while SpotAPI discovers and caches the current web-player queries.

Try the interactive terminal explorer:

```bash
python -m pip install "spotapi[demo]"
python -m spotapi discover "Daft Punk"
```

Navigate search results, artwork and Spotify links without signing in. [Discover example](https://github.com/Aran404/SpotAPI/blob/main/examples/discover.py) · [Troubleshooting](https://spotapi.readthedocs.io/en/latest/troubleshooting/)

## Explore in the terminal

The CLI goes beyond search. Inspect an artist, pull track credits, or list a public playlist:

```bash
python -m spotapi search "Daft Punk" --type artist --json
python -m spotapi get SPOTIFY_URL
python -m spotapi playlist items PLAYLIST_ID --limit 10
```

These work without a developer API key. Account operations—liked music, private playlists and control of your existing Spotify player—require your own Spotify session. See the [account guide](https://spotapi.readthedocs.io/en/latest/account/) and [player guide](https://spotapi.readthedocs.io/en/latest/player/).

### Connect: control your Spotify player

Connect brings searching, device selection, up-next, playback and a live activity log into one keyboard-friendly terminal session. It operates an existing signed-in Spotify player; it does **not** stream, download or decrypt tracks.

![SpotAPI Connect controlling a real Spotify player from the terminal](assets/cli-connect-demo.gif)

<p align="center"><sub>Connect · Search, navigate and control an existing Spotify player from your terminal. Spotify plays the audio; SpotAPI sends the controls.</sub></p>

Launch Connect:

```bash
python -m pip install "spotapi[connect,browser]"
python -m playwright install chromium
python -m spotapi connect
```

First-time browser sign-in is covered by these commands. Already use `SPOTIFY_COOKIE` or a saved Connect profile? Install only `spotapi[connect]` and skip the browser download.

Use `search Daft Punk`, `queue 1`, `pause`, `next` or `seek 1:30`. `Ctrl+P` opens the command palette. See the [Connect guide](docs/connect.md) for device selection and setup.

## See what else it can do

SpotAPI also powers **Studio**, a desktop music explorer built on the same library. Open tracks, inspect credits, follow artists and albums, and display timed lyrics. With a connected Spotify player, clicking a lyric can seek playback to that line.

![SpotAPI Studio desktop application preview](examples/studio/preview.png)

[Watch the synchronized-lyrics demo (GIF, about 11 MB)](assets/lyrics-sync-demo.gif) · Studio itself does not stream full Spotify tracks.

```bash
python -m pip install "spotapi[studio]"
python -m spotapi studio
```

Studio uses a native WebView. [Studio setup](https://spotapi.readthedocs.io/en/latest/studio/) explains platform requirements and Spotify sign-in. Lyric availability depends on the source and account entitlements; seeking needs an authenticated, controllable player.

## Support SpotAPI

Sponsors help keep SpotAPI free and fund maintenance, testing and documentation. [Become a sponsor](SPONSORSHIP.md).

<details open>
<summary><strong>Sponsors</strong></summary>

<!-- Each sponsor gets a separate table. Add new cards before the closing details tag. -->

<table>
  <tr>
    <td width="100%">
      <p align="center"><a href="https://www.rapidproxy.io/?code=Z89BQULDV"><img src="assets/sponsors/rapidproxy.webp" width="220" alt="RapidProxy"></a></p>
      <p>Reliable residential proxies for Python automation and web data collection. 90M+ IPs, global targeting, rotating &amp; sticky sessions, and HTTP(S)/SOCKS5 support.</p>
      <sub>Paid sponsor · Affiliate link. SpotAPI may earn a commission from purchases.</sub>
    </td>
  </tr>
</table>

</details>

## Build with Python

Reuse a catalogue session for related operations:

```python
import asyncio
from spotapi import Catalogue


async def main() -> None:
    async with Catalogue() as spotify:
        results = await spotify.search("Daft Punk")
        if results.artists:
            artist = await spotify.get_artist(results.artists[0].uri)
            print(artist.name)


asyncio.run(main())
```

**Working with large playlists?** [Audit up to 10,000 playlist occurrences](examples/playlist_audit.py), identify duplicate tracks and unavailable entries, and export a CSV. The example pages through results instead of loading the whole playlist into memory. Run it from a repository checkout.

### Where to go next

| Build | Start here |
|---|---|
| Music search or public metadata tools | [Public catalogue](https://spotapi.readthedocs.io/en/latest/catalogue/) |
| A playlist organizer that handles duplicate tracks correctly | [Playlist API](https://spotapi.readthedocs.io/en/latest/account/) |
| A live now-playing display or controller | [Player example](https://github.com/Aran404/SpotAPI/blob/main/examples/player.py) |
| A personal music dashboard | [Account and statistics](https://spotapi.readthedocs.io/en/latest/account/) |
| A DJ crate using tempo and harmonic keys | [Playlist crate](https://github.com/Aran404/SpotAPI/blob/main/examples/playlist_crate.py) |
| An experimental local music recommender | [Taste Lab](https://github.com/Aran404/SpotAPI/blob/main/examples/taste_lab/README.md) |

## Why SpotAPI?

- **Start without credentials.** Public catalogue search and metadata require no Spotify developer app.
- **Typed, async results.** Work with Python models instead of guessing dictionary keys.
- **Explicit I/O.** Reading a model doesn't silently trigger another HTTP request.
- **More than read-only metadata.** With your authenticated session, manage saved music, edit playlist occurrences and control existing players.
- **Designed for exploration.** Use the CLI, Discover and Studio to understand capabilities before integrating them into code.

SpotAPI uses unofficial Spotify web-player endpoints, so behavior can change when Spotify changes those endpoints. It is **not** a substitute for the official Web API in every use case, and public-data access is different from authenticated playback access. [Compare the APIs](https://spotapi.readthedocs.io/en/latest/from-spotipy/) · [Verification boundaries](https://spotapi.readthedocs.io/en/latest/release-checks/#boundaries)

## Documentation and migration

[Quickstart](https://spotapi.readthedocs.io/en/latest/quickstart/) · [API reference](https://spotapi.readthedocs.io/en/latest/reference/) · [Coming from Spotipy](https://spotapi.readthedocs.io/en/latest/from-spotipy/) · [CLI and discovery](https://spotapi.readthedocs.io/en/latest/discovery/) · [Troubleshooting](https://spotapi.readthedocs.io/en/latest/troubleshooting/)

**Upgrading from v1?** SpotAPI 2 is async-first and contains breaking changes. Existing v1 apps can pin `spotapi==1.2.8` while migrating, or use `SyncCatalogue` for new synchronous scripts. Read the [migration guide](MIGRATION.md).

## Contributing

Bug reports, reproducible issues and thoughtful contributions are welcome. [Contributing](CONTRIBUTING.md) · [Tests](tests/README.md) · [Legal notice](LEGAL_NOTICE.md) · [GPL-3.0](LICENSE)

If SpotAPI helps you build something, **[star the repository](https://github.com/Aran404/SpotAPI)** to help other developers discover it.
