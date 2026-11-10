"""Find the tracks two public playlists have in common."""

import asyncio

from spotapi import Public


async def tracks(uri: str) -> dict[str, str]:
    result: dict[str, str] = {}

    async for page in Public.get_playlist_tracks(uri):
        result.update((track.uri, track.name) for track in page)

    return result


async def main() -> None:
    left, right = await asyncio.gather(
        tracks("37i9dQZF1DXcBWIGoYBM5M"), tracks("37i9dQZEVXbMDoHDwVN2tF")
    )

    shared = left.keys() & right.keys()

    print(f"{len(shared)} shared tracks")

    for uri in sorted(shared):
        print(left[uri], uri)


if __name__ == "__main__":
    asyncio.run(main())
