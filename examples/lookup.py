"""Look up a track from a shared Spotify URL."""

import asyncio

from spotapi import Public


async def main() -> None:
    track = await Public.get_track(
        "https://open.spotify.com/track/39MK3d3fonIP8Mz9oHCTBB?si=shared"
    )

    print(track.name, track.uri)


if __name__ == "__main__":
    asyncio.run(main())
