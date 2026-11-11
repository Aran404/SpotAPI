"""Search first, then inspect the artist behind the first result."""

import asyncio

from spotapi import Public


async def main() -> None:
    results = await Public.search("Daft Punk", limit=5)

    for track in results.tracks:
        print(track.name, track.uri)

    if results.artists:
        artist = await Public.get_artist(results.artists[0].uri)

        if artist.stats:
            print(f"{artist.name}: {artist.stats.monthly_listeners:,} monthly listeners")

        if artist.discography and artist.discography.top_tracks:
            for item in artist.discography.top_tracks.items:
                print(item.track.name, item.track.playcount)


if __name__ == "__main__":
    asyncio.run(main())
