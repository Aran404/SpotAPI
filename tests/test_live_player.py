"""Explicitly enabled, low-frequency checks that never control playback."""

import asyncio
import os

import pytest

from spotapi import AsyncClient, LyricsClient, PlayerStatus

pytestmark = [pytest.mark.live, pytest.mark.authenticated]


async def test_live_authenticated_status_snapshot() -> None:
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        status = PlayerStatus(client)
        ready = asyncio.Event()

        @status.event
        async def on_ready() -> None:
            ready.set()

        async with status.connect():
            await asyncio.wait_for(ready.wait(), 5)

            assert status.connection_id
            assert status.state is not None
            assert all(device.id and device.name for device in status.devices)


async def test_live_premium_lyrics() -> None:
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        lyrics = await LyricsClient(client).get(
            "33XUHrCbrAW6me9ewdCZip",
            image_url="https://i.scdn.co/image/ab67616d0000b27310f5b59ee71a232bc0681445",
        )

        assert lyrics.lines and any(line.words for line in lyrics.lines)
        assert all(isinstance(line.start_time_ms, int) for line in lyrics.lines)
