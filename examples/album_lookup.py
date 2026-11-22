"""Look up an album and print its pre-release end date and track count."""

import asyncio

from spotapi import Public


async def main() -> None:
    album = await Public.get_album("spotify:album:3LUcDBe7DZDExhHbZEQchk")
    end = album.pre_release_end_date_time

    print(album.name)
    print("Pre-release end:", end.iso_string if end else None, end.precision if end else None)
    print("Tracks:", album.tracks_v2.total_count if album.tracks_v2 else len(album.tracks))


if __name__ == "__main__":
    asyncio.run(main())
