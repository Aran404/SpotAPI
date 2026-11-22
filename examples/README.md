# Build with SpotAPI

The command-line tools, Discover, Connect and Studio are usable applications.
**These examples show why you might want the Python library itself:** repeat
work, transform results, combine datasets, or integrate music metadata into an
application you build.

Install the current library from PyPI with `python -m pip install spotapi`,
then run these scripts from a clone of the repository. Public-catalogue reads
need no Spotify developer key. Account-scoped operations require your own
authenticated session.

| What you're building | Example | Notes |
|---|---|---|
| First public search | [public_search.py](public_search.py) | Typed results and predictable field names |
| Album lookup with pre-release end date | [album_lookup.py](album_lookup.py) | Prints name, pre-release end date and track count for one album |
| CSV audit of a large public playlist | [playlist_audit.py](playlist_audit.py) | Keeps duplicate occurrences and unavailable entries; bounded to 10,000 |
| Playlist overlap analysis | [overlap.py](overlap.py) | Compare shared tracks without editing either playlist |
| Artist and recording credits | [credit_trail.py](credit_trail.py) | Inspect contributors and related metadata |
| A tempo/key-informed DJ crate | [playlist_crate.py](playlist_crate.py) | Optional metadata, requires the `rich` package for table output |
| Live player integration | [player.py](player.py) | Requires your own Spotify session and an existing player |
| Local playlist recommendations | [taste_lab/](taste_lab/README.md) | Experimental; follow its own dependency and validation instructions |

## Example: audit a playlist

```sh
python examples/playlist_audit.py "spotify:playlist:PLAYLIST_ID" --output playlist.csv
```

This reads entries incrementally and keeps duplicate track occurrences as
separate rows. The script never overwrites an existing CSV, and it reports
track/episode/unavailable counts. It does **not** bypass Spotify's access
controls or avoid service limits.

For repeated queries, use `async with Catalogue() as spotify:` to reuse a
session, rather than opening one client for every result. For one-off requests,
`Public` provides convenient methods that close their owned connection.

The main [README](../README.md) explains installation and optional interfaces.
The [catalogue guide](../docs/catalogue.md), [account guide](../docs/account.md),
and [API reference](../docs/reference.md) explain the Python interfaces.

SpotAPI relies on unofficial Spotify services that can change. Treat missing
metadata as unknown; respect applicable terms; never share account cookies.
