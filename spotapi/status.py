"""Observe account-wide playback through a scoped Spotify dealer connection."""

from __future__ import annotations

import asyncio
import json
import math
import platform
import secrets
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable, Coroutine, Mapping
from contextlib import asynccontextmanager
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Literal, ParamSpec, Self, TypeVar, overload
from urllib.parse import urlencode

import wreq

from spotapi.models.playback import Device, PlaybackUpdate, PlayerState

from ._parsing import integer, mapping, records
from ._protocol.routes import CONNECT_OBSERVER
from .client import AsyncClient
from .connect import ConnectEndpoints
from .connection import WebSocketClient
from .datastruct import EventDispatcher
from .devices import RegisteredDevice
from .session import AuthSession
from .types import BaseClientError, HTTPError

try:
    _client_version = "spotapi:" + version("spotapi")
except PackageNotFoundError:
    _client_version = "spotapi:dev"


P = ParamSpec("P")
R = TypeVar("R")


class PlayerStatus:
    """Observe Spotify Connect state and dispatch asynchronous event callbacks.

    Register listeners before entering ``async with status.connect()``.
    ``start()`` instead supervises reconnection until ``close()``. Each scope
    owns its socket, controller registration and callback tasks; the supplied
    authentication session remains the caller's responsibility.

    Args:
        session: Authorized client or session to borrow.
        name: Nonempty name for the control-only registration.

    Attributes:
        state: Latest player snapshot, or ``None`` before one arrives.
        devices: Devices advertised by the latest cluster update.
        playback: Latest renderer state-machine update, when available.

    Note:
        Callbacks run in independent tasks. They must not block the event loop;
        pending callback work is bounded and excess callbacks may be dropped.
    """

    __slots__ = (
        "http",
        "name",
        "session",
        "controller_id",
        "observer_id",
        "_controller",
        "_controller_task",
        "state",
        "devices",
        "playback",
        "endpoints",
        "connection_id",
        "_events",
        "_waiters",
        "_acks",
        "_ack_received",
        "_handshake",
        "_snapshot",
        "_disconnected",
        "_connecting",
        "_closing",
        "_closed",
        "_scope_active",
        "_ready",
        "_stop",
        "_shutdown_lock",
        "_websocket",
        "_runner",
        "_error",
    )

    def __init__(self, session: AuthSession | AsyncClient, *, name: str = "SpotAPI") -> None:
        """Borrow a session and prepare a scoped, non-rendering Connect controller."""
        if not name.strip():
            raise ValueError("A controller name is required")

        self.name = name
        self.session = session.session if isinstance(session, AsyncClient) else session
        self.http = self.session.client
        self.controller_id = secrets.token_hex(20)
        self.observer_id = "hobs_" + self.controller_id[:32]
        self._controller: RegisteredDevice | None = None
        self._controller_task: asyncio.Task[None] | None = None

        self.state: PlayerState | None = None
        self.devices: tuple[Device, ...] = ()
        self.playback: PlaybackUpdate | None = None

        self.endpoints: ConnectEndpoints | None = None
        self.connection_id: str | None = None

        self._events = EventDispatcher()
        self._waiters: set[asyncio.Future[Any]] = set()
        self._acks: deque[str] = deque(maxlen=128)
        self._ack_received = asyncio.Event()
        self._handshake = asyncio.Event()
        self._snapshot = asyncio.Event()
        self._disconnected = asyncio.Event()

        self._connecting = False
        self._closing = False
        self._closed = False
        self._scope_active = False
        self._ready = asyncio.Event()
        self._stop = asyncio.Event()
        self._shutdown_lock = asyncio.Lock()
        self._websocket: WebSocketClient | None = None
        self._runner: asyncio.Task[Any] | None = None
        self._error: Exception | None = None

    def event(
        self, callback: Callable[P, Coroutine[Any, Any, R]]
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        """Register an async on_event callback and return it unchanged."""
        self.add_listener(callback)

        return callback

    def listen(
        self, name: str | None = None
    ) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
        """Create a decorator for an event name or an on_event callback name."""

        def decorate(
            callback: Callable[P, Coroutine[Any, Any, R]],
        ) -> Callable[P, Coroutine[Any, Any, R]]:
            """Register the callback under the selected event name and return it unchanged."""
            self.add_listener(callback, name)

            return callback

        return decorate

    def add_listener(
        self, callback: Callable[..., Coroutine[Any, Any, object]], name: str | None = None
    ) -> None:
        """Register an additional async listener for a named dealer event."""
        self._events.register(callback, (name or callback.__name__).removeprefix("on_"))

    def remove_listener(
        self, callback: Callable[..., Coroutine[Any, Any, object]], name: str | None = None
    ) -> None:
        """Remove a specific async listener without removing other subscribers."""
        self._events.unregister(callback, (name or callback.__name__).removeprefix("on_"))

    @overload
    async def wait_for(
        self,
        event: Literal["pause", "resume", "queue_change", "options_change"],
        *,
        check: Callable[[PlayerState], bool] | None = None,
        timeout: float | None = None,
    ) -> PlayerState: ...

    @overload
    async def wait_for(
        self,
        event: str,
        *,
        check: Callable[..., bool] | None = None,
        timeout: float | None = None,
    ) -> Any: ...

    async def wait_for(
        self,
        event: str,
        *,
        check: Callable[..., bool] | None = None,
        timeout: float | None = None,
    ) -> Any:
        """Wait for the next matching event; multiple arguments return a tuple."""
        if self._closing:
            raise RuntimeError("Status is closing")

        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()

        async def receive(*args: object) -> None:
            """Parse a dealer message and update its typed snapshots and events."""
            if future.done():
                return

            try:
                if check is not None and not check(*args):
                    return
            except Exception as error:
                future.set_exception(error)

                return

            future.set_result(args[0] if len(args) == 1 else args or None)

        self.add_listener(receive, event)
        self._waiters.add(future)

        try:
            return await asyncio.wait_for(future, timeout)
        finally:
            self.remove_listener(receive, event)
            self._waiters.discard(future)

    async def wait_until_disconnected(self) -> None:
        """Wait until the current dealer connection ends."""
        await self._disconnected.wait()

        if self._error is not None:
            raise BaseClientError("Dealer connection failed") from self._error

    async def wait_for_ack(self, ack_id: str, *, timeout: float = 10) -> None:
        """Wait for a target device's dealer acknowledgement, including an early reply."""
        if not ack_id:
            raise ValueError("An acknowledgement ID is required")

        if not self.is_ready:
            raise RuntimeError("Status is not ready")

        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")

        connection = self.connection_id

        async with asyncio.timeout(timeout):
            while ack_id not in self._acks:
                if self._closing or self.connection_id != connection:
                    raise RuntimeError("Connection closed before command acknowledgement")

                self._ack_received.clear()
                await self._ack_received.wait()

    @property
    def is_ready(self) -> bool:
        """Report whether the dealer handshake and initial snapshot completed."""
        return self._ready.is_set() and not self._closing and not self._disconnected.is_set()

    @property
    def is_closed(self) -> bool:
        """Report whether the observer has finished shutting down."""
        return self._closed

    async def wait_until_ready(self) -> None:
        """Wait for readiness, including across managed reconnection attempts.

        This wait has no timeout and does not observe the task running
        ``start()``. Bound it with ``asyncio.timeout`` or race that task when
        startup failure must interrupt the wait.
        """
        await self._ready.wait()

    async def close(self) -> None:
        """Stop a managed listener or close the current connection scope."""
        stopping = self._stop.is_set()
        self._stop.set()
        runner = self._runner

        if not stopping and runner is not None and runner is not asyncio.current_task():
            runner.cancel()

        await self._shutdown()

    async def start(self, *, reconnect: bool = True) -> None:
        """Listen until close(), reconnecting with bounded backoff on transient failures."""
        if self._runner is not None or self._scope_active:
            raise RuntimeError("Status already has an active listener")

        self._stop.clear()
        self._runner = asyncio.current_task()
        delay = 1.0
        connected = False

        try:
            while not self._stop.is_set():
                started = time.monotonic()

                try:
                    async with self.connect():
                        if connected:
                            self._events.dispatch("reconnect")

                        connected = True

                        await self.wait_until_disconnected()
                except Exception as error:
                    if not reconnect or not self._transient(error):
                        raise

                    self._events.dispatch("error", error)

                if not reconnect or self._stop.is_set():
                    return

                if time.monotonic() - started >= 30:
                    delay = 1.0

                try:
                    await asyncio.wait_for(self._stop.wait(), delay)
                except TimeoutError:
                    delay = min(delay * 2, 30)
        except asyncio.CancelledError:
            if not self._stop.is_set():
                raise

            current = asyncio.current_task()

            if current is not None and current.uncancel():
                raise
        finally:
            self._runner = None

            for waiter in self._waiters:
                waiter.cancel()

    @staticmethod
    def _transient(error: BaseException) -> bool:
        """Identify transport failures eligible for bounded reconnection."""
        current: BaseException | None = error

        while current is not None:
            if isinstance(current, HTTPError) and current.status_code is not None:
                return current.status_code in {408, 429, 500, 502, 503, 504}

            if isinstance(
                current,
                (
                    ConnectionError,
                    TimeoutError,
                    wreq.exceptions.ConnectionError,
                    wreq.exceptions.TimeoutError,
                ),
            ):
                return True

            current = current.__cause__

        return False

    @asynccontextmanager
    async def connect(self, *, timeout: float = 15) -> AsyncGenerator[Self, None]:
        """Open one dealer connection and wait for its initial playback snapshot.

        Args:
            timeout: Positive, finite wait in seconds for each handshake and
                initial-snapshot phase. HTTP calls retain their own timeouts.

        Yields:
            This observer after readiness. Register event listeners before entry.

        Raises:
            RuntimeError: A connection scope or startup attempt is already active.
            ValueError: The timeout is not positive and finite.
            TimeoutError: A handshake or snapshot does not arrive in time.

        Note:
            Exit closes the socket and owned registrations, callbacks and timers.
            The supplied authentication session remains borrowed. For automatic
            reconnection, use ``start()`` instead of reopening this scope manually.
        """
        if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be positive and finite")

        if self._scope_active:
            raise RuntimeError("Status is already connected or connecting")

        self._scope_active = True
        self._closed = False
        self._closing = False

        if self._runner is None:
            self._stop.clear()

        self._handshake.clear()
        self._snapshot.clear()
        self._disconnected.clear()
        self._ready.clear()
        self._acks.clear()

        self.connection_id = None
        self._error = None
        self.state, self.devices, self.playback = None, (), None
        self._connecting = True

        try:
            websocket = self._create_websocket()
            self._websocket = websocket
            self.endpoints = await ConnectEndpoints.resolve(self.session)

            if self._closed:
                raise asyncio.CancelledError("Status was closed during connection")

            url = (
                self.endpoints.dealer
                + "/?"
                + urlencode({"access_token": self.session.token.access_token})
            )

            async with websocket.connect(url, headers={"origin": "https://open.spotify.com"}):
                if self._closed:
                    raise asyncio.CancelledError("Status was closed during connection")

                await asyncio.wait_for(self._handshake.wait(), timeout)

                error: BaseException | None = None

                try:
                    await self._register_controller()
                    await self.refresh()
                    await asyncio.wait_for(self._snapshot.wait(), timeout)
                    self._ready.set()
                    self._events.dispatch("ready")

                    yield self
                except BaseException as exc:
                    error = exc
                    raise
                finally:
                    try:
                        await self._shutdown()
                    except Exception as cleanup:
                        if error is not None:
                            raise error from cleanup

                        raise
        finally:
            self._scope_active = False

            await self._shutdown()

    async def _shutdown(self) -> None:
        """Cancel owned tasks and close the dealer before deregistration."""
        async with self._shutdown_lock:
            if self._closed:
                return

            self._closing = True
            self._ready.clear()
            self._ack_received.set()
            keep_alive, self._controller_task = self._controller_task, None

            if keep_alive is not None:
                keep_alive.cancel()
                await asyncio.gather(keep_alive, return_exceptions=True)

            await self._events.close()

            try:
                await self._unregister()
            finally:
                websocket, self._websocket = self._websocket, None

                try:
                    if websocket is not None:
                        await websocket.close()
                finally:
                    self._connecting = False
                    self._closed = True
                    self._disconnected.set()

                    if self._runner is None or self._stop.is_set():
                        for waiter in self._waiters:
                            waiter.cancel()

    def _create_websocket(self) -> WebSocketClient:
        """Create dealer callbacks for the current connection attempt."""
        websocket = WebSocketClient(http_client=self.http.transport)

        websocket.start_pinging(interval=30)

        @websocket.event("message")
        async def receive(message: wreq.Message) -> None:
            """Parse a dealer message and update its typed snapshots and events."""
            if message.text is not None:
                try:
                    packet: object = json.loads(message.text)
                except (ValueError, UnicodeError):
                    self._events.dispatch("error", BaseClientError("Invalid dealer JSON"))

                    return

                self.process_message(mapping(packet))

        @websocket.event("close")
        async def disconnected() -> None:
            """Wake waiters and the connection supervisor after dealer disconnect."""
            self._disconnected.set()
            self._events.dispatch("disconnect")

        @websocket.event("error")
        async def failed(error: Exception) -> None:
            """Retain the connection failure and wake the connection supervisor."""
            self._error = error

            self._disconnected.set()
            self._events.dispatch("error", error)

        return websocket

    async def _register_controller(self) -> None:
        """Register this controller against the active dealer connection."""
        if self.connection_id is None:
            raise RuntimeError("Dealer handshake has not completed")

        self._controller = await RegisteredDevice.create(
            self.session,
            connection_id=self.connection_id,
            device_id=self.controller_id,
            name=self.name,
            client_version=_client_version,
            platform_identifier=f"python {platform.python_version()}",
            capabilities={
                "change_volume": False,
                "enable_play_token": False,
                "play_token_lost_behavior": "pause",
                "supports_file_media_type": False,
                "disable_connect": True,
                "audio_podcasts": False,
                "video_playback": False,
                "manifest_formats": [],
                "supports_preferred_media_type": False,
                "supports_playback_offsets": False,
                "supports_playback_speed": False,
            },
        )

        if self._controller.keep_alive_seconds > 0:
            self._controller_task = asyncio.create_task(
                self._keep_controller_alive(self._controller),
                name="spotapi-controller-keepalive",
            )
            self._controller_task.add_done_callback(self._controller_stopped)

    async def _keep_controller_alive(self, controller: RegisteredDevice) -> None:
        """Refresh the owned controller registration until shutdown."""
        while True:
            await asyncio.sleep(controller.keep_alive_seconds)
            await controller.report(
                state_ref=None,
                sub_state={
                    "playback_speed": 0,
                    "format": "file_urls_external",
                    "is_video_on": False,
                },
                debug_source="keep_alive",
            )

    def _controller_stopped(self, task: asyncio.Task[None]) -> None:
        """Observe controller task failure and wake the connection supervisor."""
        if task.cancelled():
            return

        error = task.exception()

        if error is not None:
            failure = BaseClientError("Controller keep-alive failed")
            failure.__cause__ = error
            self._error = failure

            self._disconnected.set()
            self._events.dispatch("error", failure)

    async def refresh(self) -> PlayerState | None:
        """Request a full snapshot; ordinary property reads never make requests."""
        if (
            self._closing
            or not self._connecting
            or self.connection_id is None
            or self.endpoints is None
        ):
            raise RuntimeError("Status is not connected")

        response = await self.http.put(
            CONNECT_OBSERVER.url(base=self.endpoints.spclient, device=self.observer_id),
            authorized=True,
            headers={
                "x-spotify-connection-id": self.connection_id,
            },
            json={
                "member_type": "CONNECT_STATE",
                "device": {
                    "device_info": {
                        "capabilities": {
                            "can_be_player": False,
                            "hidden": True,
                            "needs_full_player_state": True,
                        }
                    }
                },
            },
            max_attempts=1,
        )

        if response.json is not None:
            self._update_cluster(mapping(response.json.get("cluster", response.json)))

        return self.state

    async def _unregister(self) -> None:
        """Remove only this observer's Connect registration."""
        if self.endpoints is None:
            return

        try:
            await self.http.delete(
                CONNECT_OBSERVER.url(base=self.endpoints.spclient, device=self.observer_id),
                expected_statuses=(404,),
                authorized=True,
                max_attempts=1,
            )

        finally:
            controller, self._controller = self._controller, None

            if controller is not None:
                await controller.close()

    def process_message(self, packet: Mapping[str, Any]) -> None:
        """Apply a decoded dealer envelope, including replayed captures."""
        if self._closing:
            return

        for key, value in mapping(packet.get("headers")).items():
            if key.lower() == "spotify-connection-id" and isinstance(value, str):
                self.connection_id = value

                self._handshake.set()

        for payload in records(packet.get("payloads")):
            if "cluster" in payload:
                self._update_cluster(mapping(payload["cluster"]))
            elif payload.get("type") == "replace_state":
                self.playback = PlaybackUpdate.from_dict(payload)

                self._events.dispatch("playback_update", self.playback)

            ack_id = payload.get("ack_id")

            if isinstance(ack_id, str) and ack_id:
                self._acks.append(ack_id)
                self._ack_received.set()
                self._events.dispatch("command_ack", ack_id)

    def _update_cluster(self, cluster: Mapping[str, Any]) -> None:
        """Update typed snapshots and dispatch only the events that changed."""
        if "player_state" not in cluster:
            return

        previous = self.state

        if previous is not None and integer(cluster.get("timestamp")) < previous.timestamp:
            return

        state = PlayerState.from_cluster(cluster)
        devices = tuple(
            Device(
                id,
                str(value.get("name", "")),
                str(value.get("device_type", "")),
                integer(value["volume"]) if "volume" in value else None,
                value.get("can_play") is True,
                id == state.active_device_id,
                mapping(value.get("capabilities")).get("is_controllable"),
                mapping(value.get("capabilities")).get("volume_steps"),
            )
            for id, raw in mapping(cluster.get("devices")).items()
            if (value := mapping(raw))
        )

        if previous == state and devices == self.devices:
            return

        old_devices, self.devices = self.devices, devices
        self.state = state

        self._snapshot.set()

        if devices != old_devices:
            self._events.dispatch("devices_change", devices)
            old_volumes = {device.id: device.volume_percent for device in old_devices}

            for device in devices:
                if device.id in old_volumes and old_volumes[device.id] != device.volume_percent:
                    self._events.dispatch(
                        "volume_change", device, old_volumes[device.id], device.volume_percent
                    )

        if previous != state:
            self._events.dispatch("state_update", previous, state)

        if previous is not None:
            if previous.shuffle != state.shuffle:
                self._events.dispatch("shuffle_change", previous.shuffle, state.shuffle)

            if previous.repeat_mode != state.repeat_mode:
                self._events.dispatch("repeat_change", previous.repeat_mode, state.repeat_mode)

            if previous.playback_speed != state.playback_speed:
                self._events.dispatch(
                    "speed_change", previous.playback_speed, state.playback_speed
                )

            if previous.quality != state.quality:
                self._events.dispatch("quality_change", previous.quality, state.quality)

            if previous.context_uri != state.context_uri:
                self._events.dispatch("context_change", previous.context_uri, state.context_uri)

            if previous.position != state.position:
                self._events.dispatch("position_change", previous.position, state.position)

            if (
                previous.next_tracks != state.next_tracks
                or previous.prev_tracks != state.prev_tracks
            ):
                self._events.dispatch("queue_change", state)

            if (previous.shuffle, previous.repeat_context, previous.repeat_track) != (
                state.shuffle,
                state.repeat_context,
                state.repeat_track,
            ):
                self._events.dispatch("options_change", state)

            before, after = previous.track, state.track
            before_uri = before.uri if before else None
            after_uri = after.uri if after else None
            occurrence_changed = bool(
                before and after and before.uid and after.uid and before.uid != after.uid
            )

            if before_uri != after_uri or occurrence_changed:
                self._events.dispatch("track_change", before, after)

            if previous.is_paused != state.is_paused:
                self._events.dispatch("pause" if state.is_paused else "resume", state)

            if previous.active_device_id != state.active_device_id:
                self._events.dispatch(
                    "device_change", previous.active_device_id, state.active_device_id
                )
