import asyncio
import os

from spotapi import Player, Private

COOKIE = os.environ["SPOTIFY_COOKIE"]


async def main() -> None:
    async with Private.from_cookies(COOKIE) as spotify:
        player = Player(spotify.session)
        async with player.connect():
            await player.next()


if __name__ == "__main__":
    asyncio.run(main())
