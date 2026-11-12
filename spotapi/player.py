"""Control existing Spotify Connect players with explicitly scoped status."""

from __future__ import annotations

import asyncio
import math
import secrets
import time
from collections.abc import Mapping, Sequence
from typing import Any, Literal

from spotapi.models.history import RecentItem
from spotapi.models.playback import Device, PlaybackTrack, PlayerState

from ._protocol.routes import CONNECT_OBSERVER, CONNECT_ROUTES
from .client import AsyncClient
from .command_state import command_applied
from .connection import Response
from .devices import RegisteredDevice
from .history import ListeningHistory
from .library import LikedTracks
from .resources import SpotifyResource, parse_spotify_resource
from .session import AuthSession
from .status import PlayerStatus


def _validate_device_id(value: str) -> None:
    """Require a full playback device ID; HOBS identifiers are observers."""
    if not value or value.startswith("hobs_"):
        raise ValueError("Use a full playback device ID, not a HOBS observer ID")


def queue_resource(value: str) -> SpotifyResource:
    """Normalize a playable track or episode; reject collection resources."""
    resource = parse_spotify_resource(
        value, "track" if ":" not in value and "/" not in value else None
    )

    if resource.kind not in {"track", "episode"}:
        raise ValueError("Queue a track or episode, not a collection")

    return resource


def queue_entry(value: str | PlaybackTrack) -> dict[str, Any]:
    """Build a native queue entry, preserving an existing occurrence UID."""
    if isinstance(value, str):
        return {
            "uri": queue_resource(value).uri,
            "provider": "queue",
            "metadata": {"is_queued": "true"},
        }

    item: dict[str, Any] = {
        "uri": value.uri,
        "provider": value.provider or "context",
        "metadata": {"is_queued": "true"} if value.provider == "queue" else {},
    }

    if value.uid is not None:
        item["uid"] = value.uid

    return item


class Player(PlayerStatus):
    """Observe and control an existing Spotify device using a borrowed session.

    Enter ``player.connect()`` before sending commands, or run ``start()`` for
    managed reconnection. Property reads use local snapshots. Commands are sent
    once; an ambiguous failure requires checking fresh state before retrying.
    This client controls playback and does not decode or render audio.

    Args:
        session: Authorized client or session; its lifetime stays with the caller.
        device: Target playback device or full device ID. Defaults to the active
            device in the current snapshot.
        source: Optional source device ID for Connect routing.
        name: Name advertised by this instance's control-only registration.
    """

    __slots__ = (
        "target_device_id",
        "source_device_id",
        "_registered",
        "_sleep_task",
        "_sleep_deadline",
        "library",
        "history",
    )

    def __init__(
        self,
        session: AuthSession | AsyncClient,
        *,
        device: str | Device | None = None,
        source: str | None = None,
        name: str = "SpotAPI",
    ) -> None:
        """Borrow a session and optionally select existing source and target devices."""
        super().__init__(session, name=name)

        self.target_device_id = device.id if isinstance(device, Device) else device
        self.source_device_id = source

        for value in (self.target_device_id, self.source_device_id):
            if value is not None:
                _validate_device_id(value)

        self._registered: dict[str, RegisteredDevice] = {}
        self._sleep_task: asyncio.Task[None] | None = None
        self._sleep_deadline: float | None = None
        self.library = LikedTracks(self.session)
        self.history = ListeningHistory(self.session)

    def select(self, device: str | Device) -> None:
        """Select a target device locally; transfer playback explicitly when needed."""
        value = device.id if isinstance(device, Device) else device

        _validate_device_id(value)

        self.target_device_id = value

    def _route(self, operation: str, target: str | None = None) -> str:
        """Resolve an active controller-to-device route or reject disconnected use."""
        if (
            self._closing
            or self.endpoints is None
            or not self._connecting
            or self.connection_id is None
            or not self.is_ready
        ):
            raise RuntimeError("Player is not connected; use async with player.connect()")

        active = self.state.active_device_id if self.state is not None else None
        destination = target or self.target_device_id or active
        source = self.source_device_id or active or self.controller_id

        if destination is None:
            raise ValueError("No active player; select an existing playback device")

        _validate_device_id(source)
        _validate_device_id(destination)
        return CONNECT_ROUTES[operation].url(
            base=self.endpoints.spclient, source=source, target=destination
        )

    async def command(
        self, endpoint: str, *, wait: bool = True, timeout: float = 10, **arguments: Any
    ) -> None:
        """Send one native Connect command to the selected device.

        Args:
            endpoint: Native command name, such as ``pause`` or ``seek_to``.
            wait: Wait for a matching dealer ACK or a fresh snapshot proving a
                supported command's result. False returns after HTTP acceptance.
            timeout: Positive, finite acknowledgement wait in seconds. This does
                not include the HTTP request's own timeout.
            **arguments: Native command fields; ordinary callers should prefer
                typed methods such as ``seek`` and ``set_queue``.

        Raises:
            RuntimeError: This player is not connected and ready.
            ValueError: The command, timeout or target device is invalid.
            TypeError: ``wait`` is not a boolean.
            TimeoutError: Neither acknowledgement nor state proof arrives in time.

        Note:
            Commands are never replayed automatically. An ACK can precede media
            loading; observe playback events before depending on a loaded track.
        """
        if not endpoint:
            raise ValueError("A command endpoint is required")

        if type(wait) is not bool:
            raise TypeError("wait must be a boolean")

        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")

        command: dict[str, Any] = {
            **arguments,
            "endpoint": endpoint,
            "logging_params": {
                "page_instance_ids": [],
                "interaction_ids": [],
                "command_id": secrets.token_hex(16),
            },
        }

        previous = self._selected_state()
        response = await self.http.post(
            self._route("player/command"),
            authorized=True,
            json={"command": command},
            max_attempts=1,
        )

        if wait:
            await self._acknowledge(
                response,
                timeout=timeout,
                endpoint=endpoint,
                arguments=arguments,
                previous=previous,
            )

    async def _acknowledge(
        self,
        response: Response,
        *,
        timeout: float = 10,
        endpoint: str = "",
        arguments: Mapping[str, Any] | None = None,
        previous: PlayerState | None = None,
    ) -> None:
        """Accept an ACK or a fresh state proving the command; propagate timeout without retry."""
        ack_id = response.json.get("ack_id") if response.json is not None else None

        async def confirmed_state() -> None:
            """Wait for a new snapshot matching this command's requested result."""
            async with asyncio.timeout(timeout):
                while not command_applied(
                    endpoint, arguments or {}, previous, self._selected_state()
                ):
                    await self.wait_for("state_update", timeout=timeout)

        tasks = {asyncio.create_task(confirmed_state())}
        if isinstance(ack_id, str) and ack_id:
            tasks.add(asyncio.create_task(self.wait_for_ack(ack_id, timeout=timeout)))
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if not any(not task.cancelled() and task.exception() is None for task in done):
                await next(iter(done))
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    def _selected_state(self) -> PlayerState | None:
        """Return a snapshot only when it belongs to the selected active device."""
        self._route("player/command")

        if self.state is not None and self.target_device_id in (None, self.state.active_device_id):
            return self.state

        return None

    def _require_action(
        self, action: Literal["pause", "resume", "seek", "next", "previous", "shuffle"]
    ) -> None:
        """Reject actions Spotify explicitly restricts in the selected playback context."""
        state = self._selected_state()
        if state is not None and not state.allows(action):
            raise ValueError(f"Spotify does not allow {action} in this playback context")

    async def pause(self) -> None:
        """Pause the selected player, avoiding an already-paused request."""
        state = self._selected_state()

        if state is not None and state.is_paused:
            return

        self._require_action("pause")
        await self.command("pause")

    async def resume(self) -> None:
        """Resume the selected player, avoiding an already-playing request."""
        state = self._selected_state()

        if state is not None and state.is_playing and not state.is_paused:
            return

        self._require_action("resume")
        await self.command("resume")

    async def next(self) -> None:
        """Skip to the next item on the selected Spotify player."""
        self._require_action("next")
        await self.command("skip_next")

    async def previous(self) -> None:
        """Skip to the previous item on the selected Spotify player."""
        self._require_action("previous")
        await self.command("skip_prev")

    async def send_signal(self, signal_id: str) -> None:
        """Send a signal advertised by the selected player's current state."""
        state = self._selected_state()
        if state is None or signal_id not in state.signals:
            raise ValueError("The selected player does not advertise this signal")

        await self.command("signal", signal_id=signal_id)

    async def switch_to_video(self) -> None:
        """Send switch-to-video only when advertised by the active player."""
        await self.send_signal("switch-to-video")

    async def switch_to_audio(self) -> None:
        """Send switch-to-audio only when advertised by the active player."""
        await self.send_signal("switch-to-audio")

    async def seek(self, position_ms: int) -> None:
        """Seek to a nonnegative millisecond position in the current track."""
        if type(position_ms) is not int or position_ms < 0:
            raise ValueError("position_ms must be a non-negative integer")

        self._require_action("seek")
        await self.command(
            "seek_to", value=position_ms, position=position_ms, relative="beginning"
        )

    async def shuffle(self, enabled: bool) -> None:
        """Set context shuffle explicitly; avoid sending unchanged options."""
        if type(enabled) is not bool:
            raise TypeError("enabled must be a boolean")

        state = self._selected_state()

        if state is not None and state.shuffle == enabled:
            return

        self._require_action("shuffle")
        await self.command("set_shuffling_context", value=enabled)

    async def repeat(self, mode: Literal["off", "context", "track"]) -> None:
        """Set repeat to off, context or track; avoid unchanged options."""
        if mode not in {"off", "context", "track"}:
            raise ValueError("Repeat mode must be off, context or track")

        state = self._selected_state()

        if state is not None and state.repeat_mode == mode:
            return

        if state is not None:
            changes = {
                "context": (state.repeat_context, mode == "context"),
                "track": (state.repeat_track, mode == "track"),
            }
            for option, (before, after) in changes.items():
                if before != after and state.restrictions.get(
                    f"disallow_toggling_repeat_{option}_reasons"
                ):
                    raise ValueError(
                        "Spotify does not allow changing repeat in this playback context"
                    )

        await self.command(
            "set_options", repeating_context=mode == "context", repeating_track=mode == "track"
        )

    async def volume(self, percent: int) -> None:
        """Set the selected device's volume from zero to 100 percent."""
        if type(percent) is not int or not 0 <= percent <= 100:
            raise ValueError("Volume must be an integer between 0 and 100")

        await self.http.put(
            self._route("connect/volume"),
            authorized=True,
            json={"volume": round(percent * 65535 / 100)},
            max_attempts=1,
        )

    async def transfer(self, device: str | Device, *, play: bool | None = None) -> None:
        """Transfer to an existing device, preserving paused state unless play is supplied."""
        target = device.id if isinstance(device, Device) else device

        if play is not None and type(play) is not bool:
            raise TypeError("play must be a boolean or None")

        paused = self.state.is_paused if self.state is not None else True
        restore = "resume" if (not paused if play is None else play) else "pause"

        await self.http.post(
            self._route("connect/transfer", target),
            authorized=True,
            json={
                "transfer_options": {"restore_paused": restore},
                "command_id": secrets.token_hex(16),
            },
            max_attempts=1,
        )

        self.target_device_id = target

    async def play(
        self,
        value: str,
        *,
        position_ms: int = 0,
        offset: int | None = None,
        track: str | None = None,
    ) -> None:
        """Play a track, episode, album, playlist or artist from a Spotify link or URI."""
        if type(position_ms) is not int or position_ms < 0:
            raise ValueError("position_ms must be a non-negative integer")

        if offset is not None and (type(offset) is not int or offset < 0):
            raise ValueError("offset must be a non-negative integer")

        resource = parse_spotify_resource(
            value, "track" if ":" not in value and "/" not in value else None
        )

        if resource.kind not in {"track", "episode", "album", "playlist", "artist"}:
            raise ValueError("This resource cannot be played")

        options: dict[str, Any] = {"initially_paused": False, "seek_to": position_ms}

        if track is not None and offset is not None:
            raise ValueError("Choose a starting track or an offset, not both")

        if offset is not None:
            options["skip_to"] = {"track_index": offset}
        elif track is not None:
            options["skip_to"] = {"track_uri": parse_spotify_resource(track, "track").uri}

        await self.command(
            "play",
            context={"uri": resource.uri, "url": "context://" + resource.uri, "metadata": {}},
            play_origin={"feature_identifier": "spotapi", "referrer_identifier": "spotapi"},
            options=options,
        )

    async def add_to_queue(self, value: str) -> None:
        """Queue a track or episode from its ID, URL or URI."""
        await self.command("add_to_queue", track=queue_entry(value))

    async def set_queue(
        self,
        tracks: Sequence[str | PlaybackTrack],
        *,
        previous: Sequence[PlaybackTrack] | None = None,
    ) -> None:
        """Replace upcoming tracks, preserving history unless explicitly supplied."""
        if isinstance(tracks, str):
            raise TypeError("Pass a collection of tracks")
        state = self._selected_state()

        if state is None:
            raise ValueError("Select the active player before changing its queue")

        history = state.prev_tracks if previous is None else previous
        arguments: dict[str, Any] = {
            "next_tracks": [queue_entry(value) for value in tracks],
            "prev_tracks": [queue_entry(value) for value in history],
        }

        if state.queue_revision is not None:
            arguments["queue_revision"] = state.queue_revision

        await self.command("set_queue", **arguments)

    async def clear_queue(self) -> None:
        """Remove manually queued items while keeping the context and history."""
        state = self._selected_state()

        if state is None:
            raise ValueError("Select the active player before changing its queue")

        remaining = [track for track in state.next_tracks if track.provider != "queue"]

        if len(remaining) != len(state.next_tracks):
            await self.set_queue(remaining)

    async def remove_from_queue(self, value: str | PlaybackTrack) -> None:
        """Remove one occurrence, using its UID when supplied."""
        state = self._selected_state()

        if state is None:
            raise ValueError("Select the active player before changing its queue")

        uri = value.uri if isinstance(value, PlaybackTrack) else queue_resource(value).uri
        uid = value.uid if isinstance(value, PlaybackTrack) else None
        tracks = list(state.next_tracks)

        for index, item in enumerate(tracks):
            if (uid is not None and item.uid == uid) or (uid is None and item.uri == uri):
                del tracks[index]

                await self.set_queue(tracks)

                return

        raise ValueError("This occurrence is not in the upcoming queue")

    async def restart(self) -> None:
        """Seek the selected player to the beginning of its current item."""
        await self.seek(0)

    async def toggle(self) -> None:
        """Pause or resume according to the selected player's observed state."""
        state = self._selected_state()

        if state is None:
            raise ValueError("Select the active player before toggling playback")

        if state.is_paused:
            await self.resume()
        else:
            await self.pause()

    def _track_uri(self, value: str | None) -> str:
        """Normalize a supplied track or require a current music-track snapshot."""
        if value is not None:
            return parse_spotify_resource(value, "track").uri

        if (
            self.state is None
            or self.state.track is None
            or not self.state.track.uri.startswith("spotify:track:")
        ):
            raise ValueError("There is no current music track")

        return self.state.track.uri

    async def is_liked(self, track: str | None = None) -> bool:
        """Check whether a supplied or currently playing track is saved."""
        flags = await self.library.contains([self._track_uri(track)])

        return flags[0]

    async def like(self, track: str | None = None) -> None:
        """Save a supplied or currently playing music track."""
        uri = self._track_uri(track)

        await self.library.add([uri])
        self._events.dispatch("library_change", uri, True)

    async def unlike(self, track: str | None = None) -> None:
        """Unsave a supplied or currently playing music track."""
        uri = self._track_uri(track)

        await self.library.remove([uri])
        self._events.dispatch("library_change", uri, False)

    async def recents(self, *, limit: int = 20, offset: int = 0) -> tuple[RecentItem, ...]:
        """Read a bounded page of the account's recent activity."""
        return await self.history.get(limit=limit, offset=offset)

    @property
    def sleep_timer_remaining(self) -> float | None:
        """Return seconds until the owned pause timer expires, or None."""
        if self._sleep_deadline is None:
            return None

        return max(0.0, self._sleep_deadline - time.monotonic())

    async def sleep_timer(self, seconds: float | None) -> None:
        """Pause after a delay; pass None to cancel. The client must stay connected."""
        self._route("player/command")

        if seconds is not None and (
            isinstance(seconds, bool) or not math.isfinite(seconds) or seconds <= 0
        ):
            raise ValueError("seconds must be positive and finite, or None")

        await self._cancel_sleep_timer()

        if seconds is not None:
            self._sleep_deadline = time.monotonic() + seconds
            self._sleep_task = asyncio.create_task(
                self._finish_sleep_timer(seconds), name="spotapi-sleep-timer"
            )
            self._sleep_task.add_done_callback(self._sleep_timer_done)

    async def _finish_sleep_timer(self, seconds: float) -> None:
        """Wait for the owned timer and pause its selected device."""
        await asyncio.sleep(seconds)
        await self.pause()
        self._events.dispatch("sleep_timer_finished")

    def _sleep_timer_done(self, task: asyncio.Task[None]) -> None:
        """Observe timer errors without leaking unhandled task exceptions."""
        if task is self._sleep_task:
            self._sleep_task = None
            self._sleep_deadline = None

        if not task.cancelled() and (error := task.exception()) is not None:
            self._events.dispatch("error", error)

    async def _cancel_sleep_timer(self) -> None:
        """Cancel and await the owned sleep task before replacing or closing it."""
        task, self._sleep_task = self._sleep_task, None
        self._sleep_deadline = None

        if task is not None:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def register_device(
        self,
        name: str,
        *,
        client_version: str,
        platform_identifier: str,
        capabilities: Mapping[str, Any],
    ) -> str:
        """Register a device backed by your own renderer; this library does not decode audio."""
        self._route("player/command")

        assert self.endpoints is not None and self.connection_id is not None
        registration = await RegisteredDevice.create(
            self.session,
            connection_id=self.connection_id,
            name=name,
            client_version=client_version,
            platform_identifier=platform_identifier,
            capabilities=capabilities,
            endpoint=self.endpoints.playback,
        )
        self._registered[registration.id] = registration

        return registration.id

    async def report_state(
        self,
        device_id: str,
        *,
        state_ref: Mapping[str, Any] | None,
        sub_state: Mapping[str, Any],
        debug_source: str,
    ) -> None:
        """Report your registered renderer's state, with monotonic sequence numbers."""
        if self._closing or device_id not in self._registered:
            raise ValueError("Report state only for a device registered by this player")

        await self._registered[device_id].report(
            state_ref=state_ref,
            sub_state=sub_state,
            debug_source=debug_source,
        )

    async def deregister_device(
        self, device_id: str, *, observer_id: str | None = None, seq_num: int | None = None
    ) -> None:
        """Remove explicit device IDs. A HOBS ID is never inferred from a full ID."""
        if self.endpoints is None:
            raise RuntimeError("Player is not connected")

        _validate_device_id(device_id)
        registration = self._registered.get(device_id)

        if registration is None:
            if seq_num is None:
                raise ValueError("Supply seq_num when removing an external registration")

            registration = RegisteredDevice(
                self.session, device_id, endpoint=self.endpoints.playback
            )

        if observer_id is not None:
            if not observer_id.startswith("hobs_"):
                raise ValueError("observer_id must be a HOBS ID")

            await self.http.delete(
                CONNECT_OBSERVER.url(base=self.endpoints.spclient, device=observer_id),
                authorized=True,
                max_attempts=1,
            )

        await registration.close(seq_num=seq_num)
        self._registered.pop(device_id, None)

    async def _unregister(self) -> None:
        """Cancel owned timers and remove only registrations owned by this player."""
        errors: list[Exception] = []

        await self._cancel_sleep_timer()

        try:
            await super()._unregister()
        except Exception as error:
            errors.append(error)

        for device_id in tuple(self._registered):
            try:
                await self.deregister_device(device_id)
            except Exception as error:
                errors.append(error)

        if errors:
            raise ExceptionGroup("Could not remove registered devices", errors)
