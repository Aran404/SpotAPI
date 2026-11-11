"""Discover the people behind a song."""

import asyncio

from spotapi import Public


async def main() -> None:
    credits = await Public.get_track_credits("39MK3d3fonIP8Mz9oHCTBB")

    for person in credits.contributors:
        print(person.name, person.role, person.uri or "")


if __name__ == "__main__":
    asyncio.run(main())
