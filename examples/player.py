"""Watch Connect events using a locally configured Spotify Cookie header."""

import asyncio
import os
from contextlib import suppress

from spotapi import Player, Private
from spotapi.models import PlaybackTrack


async def main() -> None:
    cookie = os.environ.get("SPOTIFY_COOKIE")
    if not cookie:
        raise SystemExit("Set SPOTIFY_COOKIE to your own Spotify session. See docs/studio.md.")

    async with Private.from_cookies(cookie) as spotify:
        player = Player(spotify.session)

        @player.event
        async def on_track_change(
            before: PlaybackTrack | None, after: PlaybackTrack | None
        ) -> None:
            if after:
                print(f"{after.artist} - {after.name}")

        async with player.connect():
            print("Watching Spotify. Play a track on an existing device. Press Ctrl+C to exit.")
            if player.state and player.state.track:
                print(f"{player.state.track.artist} - {player.state.track.name}")
            await player.wait_until_disconnected()


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
