"""Search first, then inspect the artist behind the first result."""

import asyncio

from spotapi import Catalogue


async def main() -> None:
    async with Catalogue() as spotify:
        results = await spotify.search("Daft Punk", types=("track", "artist"), limit=5)

        for track in results.tracks:
            print(track.name, track.uri)

        if not results.artists:
            return

        artist = await spotify.get_artist(results.artists[0].uri)

        if artist.stats:
            print(f"{artist.name}: {artist.stats.monthly_listeners:,} monthly listeners")

        if artist.discography and artist.discography.top_tracks:
            for item in artist.discography.top_tracks.items:
                print(item.track.name, item.track.playcount)


if __name__ == "__main__":
    asyncio.run(main())
