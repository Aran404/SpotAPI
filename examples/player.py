"""Watch Connect events using a locally configured Spotify Cookie header."""

import asyncio
import os

from spotapi import AsyncClient, Player
from spotapi.models import PlaybackTrack


async def main() -> None:
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        player = Player(client)

        @player.event
        async def on_track_change(
            before: PlaybackTrack | None, after: PlaybackTrack | None
        ) -> None:
            if after:
                print(f"{after.artist} - {after.name}")

        async with player.connect():
            if player.state and player.state.track:
                print(f"{player.state.track.artist} - {player.state.track.name}")

            for device in player.devices:
                print(f"{'*' if device.is_active else ' '} {device.name}: {device.id}")

            await player.wait_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
