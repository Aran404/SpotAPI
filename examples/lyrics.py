"""Read Premium lyrics with the same authenticated client used by Connect."""

import asyncio
import os
import sys

from spotapi import AsyncClient, LyricsClient


async def main() -> None:
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        lyrics = await LyricsClient(client).get(sys.argv[1])

        print(f"{lyrics.provider}: {lyrics.sync_type}, {len(lyrics.lines)} lines")

        for line in lyrics.at(30_000):
            print(line.words)


if __name__ == "__main__":
    asyncio.run(main())
