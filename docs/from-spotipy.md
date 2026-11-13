---
description: Move public Spotify search and metadata workflows from Spotipy to SpotAPI. Compare setup, async usage, result models and important integration tradeoffs.
---

# Coming from Spotipy

Start with one public-read workflow. SpotAPI is a different integration, not a
drop-in import replacement. You can also use it alongside an existing client
for a particular feature instead of migrating an entire application.

## Public search

### Spotipy

```python
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials())
response = spotify.search(q="Daft Punk", type="track", limit=5)
for track in response["tracks"]["items"]:
    print(track["name"], track["uri"])
```

Configure your developer credentials for this official Web API flow.

### SpotAPI: async

```python
from spotapi import Public

results = await Public.search("Daft Punk", types="track", limit=5)
for track in results.tracks:
    print(track.name, track.uri)
```

This snippet runs inside an async function or a notebook supporting `await`.
Public data uses an anonymous web-player session, without a developer app.

### SpotAPI: sync

```python
from spotapi import SyncCatalogue

with SyncCatalogue() as spotify:
    results = spotify.search("Daft Punk", types="track", limit=5)
    for track in results.tracks:
        print(track.name, track.uri)
```

## Map the task, not the method spelling

| Task | Spotipy | SpotAPI |
|---|---|---|
| Search tracks | `search(q=..., type="track")` | `Public.search(..., types="track")` |
| Read a track | `track(value)` | `Public.get_track(value)` |
| Reuse an async scope | Integration-dependent | `async with Catalogue()` |
| Inspect fields | JSON dictionaries | Typed models; `to_dict` for JSON-safe export |
| Read independent URLs with failures preserved | Application-specific handling | `Public.fetch_many(urls)` |
| Page playlist occurrences | `playlist_items(...)` | `Public.get_playlist_items(...)` |
| Account/library operations | Official OAuth scopes | Explicit cookie-authenticated scope |

These are workflow mappings, not promises that the returned schemas, market
selection, error types, quotas or authentication contracts are interchangeable.
SpotAPI preserves occurrence IDs in playlist results; unavailable entries and
optional metadata need explicit handling.

## Keep the important differences visible

- Use `types=`, typed attributes, and explicit async contexts where appropriate.
- A Spotify account cookie is a credential. Account features require deliberate
  authentication; public search does not. Never commit cookies.
- Display language is not an availability-market override. Region and account
  entitlement still affect returned data.
- A timed-out mutation may already have applied. Reconcile state before retrying.
- SpotAPI relies on unofficial contracts; it does not grant permission to use
  Spotify data beyond the applicable terms or guarantee continued access.

Use the [first-result guide](quickstart.md) to verify your installation, then
port one bounded read and compare the actual data your application depends on.
If you need official authorization or contractual guarantees, keep the official
integration rather than migrating solely for shorter example code.

Spotipy example reference: [upstream quickstart](https://github.com/spotipy-dev/spotipy).
