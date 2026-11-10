"""Explicit personal-account control checks, with playback settings restored."""

import asyncio
import os
from collections.abc import Awaitable, Callable

import pytest

from spotapi import AsyncClient, Player
from spotapi.models import PlayerState

pytestmark = [pytest.mark.live, pytest.mark.authenticated, pytest.mark.mutates]


async def wait_state(player: Player, check: Callable[[PlayerState], bool]) -> PlayerState:
    refreshed = False
    loop = asyncio.get_running_loop()
    started = loop.time()

    async with asyncio.timeout(10):
        while True:
            state = player.state

            if state is not None and check(state):
                return state

            if not refreshed and loop.time() - started >= 3:
                await player.refresh()

                refreshed = True

            await asyncio.sleep(0.02)


async def test_live_queue_options_and_pause_timer_restore_original_state() -> None:
    async with (
        await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client,
        Player(client).connect() as player,
    ):
        baseline = player.state

        if baseline is None or not baseline.active_device_id or baseline.track is None:
            pytest.skip("Open an existing Spotify player with a music track ready")

        track = baseline.track
        original_position = baseline.position_ms
        original_uids = {item.uid for item in baseline.next_tracks}

        try:
            await player.pause()
            await wait_state(player, lambda state: state.is_paused)
            if baseline.allows("shuffle"):
                await player.shuffle(not baseline.shuffle)
                await wait_state(player, lambda state: state.shuffle != baseline.shuffle)

            mode = "track" if baseline.repeat_mode != "track" else "off"

            if not any(
                baseline.restrictions.get("disallow_toggling_repeat_" + option + "_reasons")
                for option in ("track", "context")
            ):
                await player.repeat(mode)
                await wait_state(player, lambda state: state.repeat_mode == mode)
            await player.add_to_queue(track.uri)
            queued = await wait_state(
                player,
                lambda state: any(
                    item.uri == track.uri and item.uid not in original_uids
                    for item in state.next_tracks
                ),
            )
            occurrence = next(
                item
                for item in queued.next_tracks
                if item.uri == track.uri and item.uid not in original_uids
            )

            assert occurrence.uid is not None

            await player.remove_from_queue(occurrence)
            await wait_state(
                player,
                lambda state: all(item.uid != occurrence.uid for item in state.next_tracks),
            )
            await player.resume()
            await wait_state(player, lambda state: state.is_playing)

            async with asyncio.TaskGroup() as tasks:
                tasks.create_task(player.wait_for("sleep_timer_finished", timeout=10))
                await asyncio.sleep(0)
                await player.sleep_timer(2)
            await wait_state(player, lambda state: state.is_paused)
        finally:
            await restore_playback(player, baseline, original_position, original_uids)


async def restore_playback(
    player: Player,
    baseline: PlayerState,
    position: int,
    original_uids: set[str | None],
) -> None:
    """Attempt every restoration step and report failures together rather than masking them."""
    errors: list[Exception] = []

    async def attempt(label: str, operation: Awaitable[None]) -> None:
        try:
            await operation
        except Exception as error:
            error.add_note("Playback restoration: " + label)
            errors.append(error)

    await attempt("cancel timer", player.sleep_timer(None))
    state = player.state
    if state is not None:
        uri = baseline.track.uri if baseline.track else None
        remaining = [
            item
            for item in state.next_tracks
            if not (item.uri == uri and item.provider == "queue" and item.uid not in original_uids)
        ]
        if len(remaining) != len(state.next_tracks):
            await attempt("remove temporary queue entry", player.set_queue(remaining))
        await attempt("restore shuffle", player.shuffle(baseline.shuffle))
        await attempt("restore repeat", player.repeat(baseline.repeat_mode))

        # Restore play/pause before seeking. The test device could acknowledge
        # a paused seek but fail to process the following resume.
        await attempt(
            "restore pause state", player.pause() if baseline.is_paused else player.resume()
        )
        before_seek = player.state
        if (
            baseline.allows("seek")
            and before_seek is not None
            and before_seek.track
            and before_seek.track.uri == uri
            and abs(before_seek.position_ms - position) >= 1500
        ):
            await attempt("restore position", player.seek(position))
            try:
                await wait_state(
                    player,
                    lambda snapshot: snapshot is not before_seek
                    and abs(snapshot.position_ms - position) < 1500,
                )
            except TimeoutError as error:
                error.add_note("Playback restoration: confirm position")
                errors.append(error)
        if not errors:
            await wait_state(
                player,
                lambda state: state.is_paused == baseline.is_paused
                and state.is_playing == baseline.is_playing,
            )
    if errors:
        raise ExceptionGroup("Playback restoration failed", errors)
