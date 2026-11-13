---
description: Search Spotify from Python without creating a developer app. Build with typed results, reusable async clients, playlist occurrence editing and player events.
---

# Build something with your music.

**Spotify tools for Python. Typed results. Async by default. No developer API key for public data.**

Search tracks, browse releases, inspect public playlists or build a live
now-playing display. Start anonymously; connect your own account when you need
saved music, playlist edits, entitled lyrics or podcast captions.

[Get your first result](quickstart.md){ .md-button .md-button--primary }
[Coming from Spotipy?](from-spotipy.md){ .md-button }

```sh
python -m pip install spotapi
spotapi search "Daft Punk"
```

Want a visual first result? Install the demo extra and run
`spotapi discover "Daft Punk"`. See
[terminal setup](quickstart.md#browse-from-your-terminal).

```python
import asyncio

from spotapi import Public


async def main() -> None:
    hits = await Public.search("Daft Punk", types="track", limit=5)
    for track in hits.tracks:
        print(track.name, track.uri)


asyncio.run(main())
```

## Pick what you want to build

| Your project | Start here |
|---|---|
| A catalogue browser or music dashboard | [Search and reusable catalogue clients](catalogue.md) |
| A release explorer or concert finder | [Discovery and artist events](discovery.md) |
| A duplicate-aware playlist organiser | [Account and playlist operations](account.md) |
| A now-playing overlay | [Player snapshots and events](player.md) |
| A working application to explore and learn from | [Studio and its source](studio.md) |
| A podcast-caption tool | [Authenticated transcripts](discovery.md#podcast-captions) |
| A Python script or notebook | [Synchronous access](quickstart.md#synchronous-scripts) |
| A local assistant integration | [Read-only MCP tools](discovery.md#local-mcp-tools) |

## Small API, explicit behavior

- Result fields have types and autocomplete. Inspecting a model never sends a request.
- Reuse one `Catalogue` for related reads, or let `Public` clean up a one-shot call.
- Batch independent resources without losing input order or individual errors.
- Choose explicit account and player scopes. Mutations are not silently replayed.

## Choose the integration that fits

SpotAPI uses unofficial Spotify web-player endpoints. It does not provide an
official API contract, unlimited access, or a legal exemption. Endpoint behavior,
rate limits, availability and entitlement can change. Official Web API clients
such as Spotipy remain useful when that integration is the right fit.

Read the [request policy](transport.md), [verification boundaries](player-coverage.md)
and [legal notice](https://github.com/Aran404/SpotAPI/blob/main/LEGAL_NOTICE.md).

If SpotAPI helped you get a useful result, [star the repository](https://github.com/Aran404/SpotAPI)
or share what you built in its Discussions. Specific bug reports and small
integration examples help other developers get started too.
