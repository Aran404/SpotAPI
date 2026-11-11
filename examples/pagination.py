"""Stop after ten tracks while closing the iterator deterministically."""

import asyncio
from contextlib import aclosing

from spotapi import Public


async def main() -> None:
    count = 0

    async with aclosing(Public.iter_tracks("Radiohead")) as tracks:
        async for track in tracks:
            print(track.name)

            count += 1

            if count == 10:
                break


if __name__ == "__main__":
    asyncio.run(main())
