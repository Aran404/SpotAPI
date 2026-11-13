# Catalogue guide

| You need | Start here |
|---|---|
| Search any catalogue category | `await Public.search(query, types=..., limit=...)` |
| Stream search pages | `Public.search_tracks(query, limit=20)` and the other category helpers |
| Resolve a Spotify URL, URI or ID | `get_track`, `get_album`, `get_artist`, `get_podcast`, `get_audiobook`, `get_playlist` |
| Look up several tracks, albums or artists | `Public.get_tracks()`, `Public.get_albums()`, `Public.get_artists()` |
| Detect a resource from a URL | `await Public.get(url)` |
| Read every playlist occurrence, including removed items | `Public.get_playlist_items` / `Public.iter_playlist_items` |
| Read album tracks in order | `Public.get_album_tracks` |
| Browse albums, singles or compilations | `Public.get_artist_releases(artist, kind="albums")` |
| Explore neighboring artists | `await Public.get_related_artists(artist)` |
| Read an artist's Discovered On selection | `await Public.get_artist_discovered_on(artist)` |
| Read artist top tracks and play counts | `await Public.get_artist_top_tracks(artist)` |
| Explore public curators and their first playlists | `await Public.get_profile(username, limit=20)` |
| Read podcast episodes | `Public.get_podcast_episodes` / `Public.iter_podcast_episodes` |
| Read audiobook chapters | `Public.get_audiobook_chapters` |
| Type your application | `from spotapi.models import Track, PlaylistDetails` |

Page helpers use `async for`; single lookups use `await`. Optional Spotify
metadata remains optional. Typed dataclasses work with `dataclasses.asdict`
and `json.dumps`. No hidden HTTP calls occur when you inspect a model.
Multi-item lookups reuse one client and run up to eight separate resource reads
at a time. They return details in input order and propagate request failures.

For advanced search inclusion options, use immutable Python fields:

```python
from spotapi import Public, SearchOptions

results = await Public.search(
    "Daft Punk",
    types=("track", "album"),
    options=SearchOptions(include_pre_releases=True),
    limit=10,
)
```

An explicit `limit` overrides the options object's page size without changing
the object. Spotify's camelCase request keys stay inside the wire conversion.

`Public` closes its client before a lookup returns and when a page stream
finishes. For several operations, reuse one connection scope:

```python
from spotapi import Catalogue

async with Catalogue() as spotify:
    results = await spotify.search("Daft Punk")
    artist = await spotify.get_artist(results.artists[0].uri)
```

When you stop a page stream early, use `contextlib.aclosing` around it.
`Catalogue.queries` exposes raw persisted queries within the same scope;
`Queries.open()` from `spotapi.queries` offers a lower-level query scope.

Catch `SpotAPIError` for library failures. Invalid arguments raise `ValueError`
or `TypeError`; cancellation propagates. The default logger uses stdlib
`logging` and does not configure your application. Mutation requests are not
replayed automatically after ambiguous failures.


For runnable introductions, see the scripts in [examples](https://github.com/Aran404/SpotAPI/blob/main/examples).

## Discovered On playlists

The development checkout adds `get_artist_discovered_on` to `Catalogue`,
`Public` and `SyncCatalogue`. It returns Spotify's bounded playlist selection
in server order; an unavailable slot is `None`. This is not an exhaustive list
of playlist placements, and no historical placements are inferred.

```python
playlists = await Public.get_artist_discovered_on(artist_url)
for playlist in playlists:
    if playlist is not None:
        print(playlist.name, playlist.uri)
```

The native response shape was observed in prior account research. Parser
fixtures cover unavailable entries and contract failures; a fresh managed-client
live check remains a release gate. Missing or changed collections raise an
error rather than becoming an empty successful result.
