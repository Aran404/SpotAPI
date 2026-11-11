"""Find the same people behind different songs, even when their credits change."""

import argparse
import asyncio
from collections import defaultdict

from spotapi import Catalogue

DEFAULT_TRACKS = ("0DiWol3AO6WpXZgp0goxAV", "5W3cjX2J3tjhG8zb6u0qHn", "7MXVkk9YMctZqd1Srtv4MB")


async def main(uris: list[str]) -> None:
    async with Catalogue() as spotify:
        tracks = await spotify.get_tracks(uris)
        async with asyncio.TaskGroup() as group:
            credits = [group.create_task(spotify.get_track_credits(track.uri)) for track in tracks]

    names: dict[str, str] = {}
    appearances: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    titles = {track.uri: track.name for track in tracks}

    for task in credits:
        song = task.result()
        for person in song.contributors:
            if person.uri and person.role:
                names.setdefault(person.uri, person.name)
                appearances[person.uri][song.uri].add(person.role)

    shared = [uri for uri, songs in appearances.items() if len(songs) > 1]
    if not shared:
        print("No shared contributor IDs found for these recordings.")

    for uri in sorted(shared, key=lambda uri: (-len(appearances[uri]), names[uri])):
        print(names[uri])
        for track_uri, roles in appearances[uri].items():
            print(f"  {titles[track_uri]}: {', '.join(sorted(roles))}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "tracks", nargs="*", metavar="TRACK", help="Spotify track IDs, links, or URIs"
    )
    args = parser.parse_args()
    uris: list[str] = args.tracks or list(DEFAULT_TRACKS)
    if not 2 <= len(uris) <= 8:
        parser.error("Pass between two and eight tracks.")
    asyncio.run(main(uris))
