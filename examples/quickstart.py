"""Search Spotify and print typed track results."""

import asyncio

from spotapi import Public


async def main() -> None:
    results = await Public.search("Daft Punk")

    for track in results.tracks:
        print(track.name, track.uri)


if __name__ == "__main__":
    asyncio.run(main())
