"""Event-driven WebSocket client with optional application-level heartbeats."""

from __future__ import annotations

import asyncio
import contextlib
import math
from collections import deque
from collections.abc import AsyncGenerator, Callable, Coroutine
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    Final,
    ParamSpec,
    Self,
    TypeAlias,
    TypeVar,
    Unpack,
)
from urllib.parse import urlsplit

import wreq

from spotapi.v2.datastruct import EventDispatcher
from spotapi.v2.types import DefaultLogger

if TYPE_CHECKING:
    from spotapi.v2.types import LoggerProtocol

    from .http import HTTPClient

__all__ = ("WebSocketClient",)

_P = ParamSpec("_P")
_R = TypeVar("_R")
CoroFunc: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]

_DEFAULT_PING_MESSAGE: Final[str] = '{"type":"ping"}'
_DEFAULT_PING_INTERVAL: Final[float] = 60.0
_READ_TIMEOUT: Final[timedelta] = timedelta(seconds=1)


async def _cancel_and_wait(task: asyncio.Task[None]) -> None:
    """Cancel and observe an owned task without hiding caller cancellation."""
    if task.done():
        if not task.cancelled():
            task.result()

        return

    current = asyncio.current_task()
    cancel_count = current.cancelling() if current is not None else 0
    caller_cancelled = False

    task.cancel()

    while not task.done():
        try:
            await asyncio.shield(task)
        except asyncio.CancelledError:
            if current is not None and current.cancelling() > cancel_count:
                caller_cancelled = True
                cancel_count = current.cancelling()
            elif not task.done():
                raise

    if caller_cancelled:
        raise asyncio.CancelledError


class _HeartbeatManager:
    """Send application-level ping messages on a background task."""

    __slots__ = (
        "_sender",
        "_dispatcher",
        "_logger",
        "_task",
        "_interval",
        "_message",
        "_connected",
        "_stopping",
    )

    def __init__(
        self,
        sender: Callable[[wreq.Message], Coroutine[Any, Any, None]],
        dispatcher: EventDispatcher,
        logger: LoggerProtocol,
    ) -> None:
        """Configure heartbeat framing and retain ownership of its background task."""
        self._sender = sender
        self._dispatcher = dispatcher
        self._logger = logger
        self._task: asyncio.Task[None] | None = None
        self._interval: float | None = None
        self._message: wreq.Message | None = None
        self._connected = False
        self._stopping: set[asyncio.Task[None]] = set()

    def start(self, interval: float, message: wreq.Message) -> None:
        """Configure a heartbeat, starting it when a socket is connected."""
        self.stop()

        self._interval = interval
        self._message = message

        self._start_if_connected()

    def connected(self) -> None:
        """Start the configured heartbeat when a socket opens."""
        self._connected = True

        self._start_if_connected()

    def _start_if_connected(self) -> None:
        """Start the heartbeat only after a native socket is attached."""
        if not self._connected or self._interval is None or self._message is None:
            return

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(
                self._loop(self._interval, self._message), name="ws-ping"
            )

    def stop(self) -> None:
        """Disable the heartbeat and request cancellation of its task."""
        self._interval = None
        self._message = None
        task, self._task = self._task, None

        if task is not None:
            self._stopping.add(task)
            task.add_done_callback(self._stopping.discard)
            task.cancel()

    async def pause(self) -> None:
        """Stop the active task while retaining its reconnect configuration."""
        self._connected = False
        task, self._task = self._task, None

        if task is not None:
            await _cancel_and_wait(task)

        for task in tuple(self._stopping):
            await _cancel_and_wait(task)

    async def _loop(self, interval: float, message: wreq.Message) -> None:
        """Send owned heartbeats until disconnect or cancellation."""
        try:
            while True:
                await asyncio.sleep(interval)
                await self._sender(message)
                self._logger.debug("Ping sent", payload=message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self._logger.error("WebSocket heartbeat failed", error_type=type(exc).__name__)
            self._dispatcher.dispatch("error", exc)


class WebSocketClient:
    """Manage a WebSocket connection and dispatch received messages.

    The connection is established by :meth:`connect`, not by constructing
    this object or entering its outer async context manager.

    Events dispatched to registered listeners are ``open``, ``message``,
    ``close`` (remote end-of-stream), and ``error``. A data prehook only
    transforms messages delivered to ``message`` listeners; :meth:`recv`
    returns the original WebSocket message.

    Args:
        http_client: HTTP client providing the underlying ``wreq.Client``.
        logger: Logger used by the event dispatcher and heartbeat manager.
        data_prehook: Optional synchronous transformer applied before
            dispatching each received WebSocket message.
    """

    __slots__ = (
        "_client",
        "_logger",
        "_ws",
        "_recv_task",
        "_recv_waiters",
        "_receive_error",
        "_connecting",
        "_last_message",
        "_data_prehook",
        "_events",
        "_heartbeat",
    )

    def __init__(
        self,
        *,
        http_client: HTTPClient,
        logger: LoggerProtocol = DefaultLogger,
        data_prehook: Callable[[wreq.Message], wreq.Message] | None = None,
    ) -> None:
        """Configure a scoped socket, borrowing an explicit HTTP client when supplied."""
        self._client: wreq.Client = http_client.wclient
        self._logger = logger
        self._data_prehook = data_prehook
        self._events = EventDispatcher(logger)
        self._heartbeat = _HeartbeatManager(self.send, self._events, logger)

        self._ws: wreq.WebSocket | None = None
        self._recv_task: asyncio.Task[None] | None = None
        self._recv_waiters: deque[asyncio.Future[wreq.Message | None]] = deque()
        self._receive_error: Exception | None = None
        self._connecting = False
        self._last_message: wreq.Message | None = None

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<WebSocketClient connected={self.is_connected}>"

    async def __aenter__(self) -> Self:
        """Return this client without opening a connection."""
        return self

    async def __aexit__(self, *_exc: object) -> None:
        """Close any connection when leaving the outer context."""
        await self.close()

    async def close(self) -> None:
        """Stop background activity and close the current connection.

        Calling this method repeatedly is safe. Closing a connection does
        not unregister listeners or clear the configured heartbeat; it resumes
        on the next connection unless :meth:`stop_pinging` was called.
        """
        await self._disconnect(close_socket=True)

    @property
    def is_connected(self) -> bool:
        """Whether this client currently owns a WebSocket object."""
        return self._ws is not None

    @property
    def last_message(self) -> wreq.Message | None:
        """Most recently dispatched message, or ``None`` after closing."""
        return self._last_message

    def _add_listener(self, func: CoroFunc, name: str | None = None) -> None:
        """Add an async socket-event callback to the dispatcher."""
        self._events.register(func, name)

    def _remove_listener(self, func: CoroFunc, name: str | None = None) -> None:
        """Remove one callback without affecting other socket listeners."""
        self._events.unregister(func, name)

    def event(self, name: str | None = None, /) -> Callable[
        [Callable[_P, Coroutine[Any, Any, _R]]],
        Callable[_P, Coroutine[Any, Any, _R]],
    ]:
        """Register an asynchronous callback for a WebSocket event.

        Args:
            name: Event name, or ``None`` to let the dispatcher infer it.

        Returns:
            A decorator that registers and returns the original callback,
            preserving its parameter types and return annotation.
        """

        def decorator(
            callback: Callable[_P, Coroutine[Any, Any, _R]],
        ) -> Callable[_P, Coroutine[Any, Any, _R]]:
            """Register and return an async websocket callback."""
            self._add_listener(callback, name)

            return callback

        return decorator

    @contextlib.asynccontextmanager
    async def connect(
        self,
        url: str,
        **kwargs: Unpack[wreq.WebSocketRequest],
    ) -> AsyncGenerator[Self, None]:
        """Open a WebSocket and run its event-dispatching receive loop.

        Args:
            url: WebSocket endpoint URL.
            **kwargs: Options forwarded to ``wreq.Client.websocket``.

        Yields:
            This client while the WebSocket context is active.

        Raises:
            RuntimeError: A connection is already open or in progress.
        """
        if self._connecting:
            raise RuntimeError("WebSocket is already connected or connecting")

        # Reserve the connection before the first await to prevent two
        # simultaneous connect() calls from passing the same check.
        self._connecting = True
        cancelled: asyncio.CancelledError | None = None

        try:
            ws = await self._client.websocket(url, **kwargs)

            self._ws = ws

            self._heartbeat.connected()

            self._receive_error = None
            self._recv_task = asyncio.create_task(
                self._receive_loop(ws), name=f"ws-recv:{urlsplit(url).hostname}"
            )

            try:
                self._events.dispatch("open")

                yield self
            except asyncio.CancelledError as exc:
                cancelled = exc
                raise
            finally:
                try:
                    await self._disconnect(close_socket=True)
                except asyncio.CancelledError as exc:
                    cancelled = exc
                    raise
        except Exception as exc:
            if cancelled is not None:
                raise cancelled from exc

            raise
        finally:
            self._connecting = False

    async def recv(self, *, timeout: float | None = None) -> wreq.Message | None:
        """Wait for the next raw message without competing with the reader.

        Incoming messages are also delivered to ``message`` listeners.
        Messages received while no call to ``recv`` is pending are not
        buffered for later calls. ``None`` indicates end-of-stream or a
        locally closed connection.

        Args:
            timeout: Maximum wait in seconds, or ``None`` to wait forever.

        Returns:
            The next original ``wreq.Message``, or ``None`` when closed.

        Raises:
            RuntimeError: No WebSocket connection is active.
            wreq.exceptions.TimeoutError: No message arrives before the timeout.
        """
        task = self._recv_task

        if task is None:
            raise RuntimeError("WebSocket is not currently connected")

        if task.done():
            if self._receive_error is not None:
                raise self._receive_error

            return None

        self._require_ws()

        waiter: asyncio.Future[wreq.Message | None] = asyncio.get_running_loop().create_future()

        self._recv_waiters.append(waiter)

        try:
            return await asyncio.wait_for(waiter, timeout=timeout)
        except TimeoutError as exc:
            # Keep the underlying wreq timeout exception part of our API.
            raise wreq.exceptions.TimeoutError("WebSocket receive timed out") from exc
        finally:
            # A cancelled/timed-out call must not consume a later message.
            with contextlib.suppress(ValueError):
                self._recv_waiters.remove(waiter)

    async def send(self, message: wreq.Message) -> None:
        """Send a WebSocket message.

        Raises:
            RuntimeError: No WebSocket connection is active.
        """
        await self._require_ws().send(message)

    def start_pinging(
        self,
        interval: float = _DEFAULT_PING_INTERVAL,
        ping_message: wreq.Message | None = None,
    ) -> None:
        """Configure periodic application-level ping messages.

        The heartbeat starts when connected and resumes after reconnecting.
        This sends a text message by default, not a WebSocket protocol ping
        frame. A later call replaces the existing heartbeat.

        Args:
            interval: Seconds between sends; must be greater than zero.
            ping_message: Message to send, or the default JSON ping text.

        Raises:
            ValueError: ``interval`` is not positive.
        """
        if isinstance(interval, bool) or not math.isfinite(interval) or interval <= 0:
            raise ValueError("ping interval must be finite and positive")

        message = (
            ping_message
            if ping_message is not None
            else wreq.Message.from_text(_DEFAULT_PING_MESSAGE)
        )

        self._heartbeat.start(interval, message)

    def stop_pinging(self) -> None:
        """Disable the periodic heartbeat, if one is configured."""
        self._heartbeat.stop()

    def _require_ws(self) -> wreq.WebSocket:
        """Require an attached native socket before reading or sending."""
        if self._ws is None:
            raise RuntimeError("WebSocket is not currently connected")

        return self._ws

    def _deliver_message(self, message: wreq.Message) -> None:
        """Wake the oldest active direct receiver, if there is one."""
        while self._recv_waiters:
            waiter = self._recv_waiters.popleft()

            if not waiter.done():
                waiter.set_result(message)

                return

    def _finish_receivers(self) -> None:
        """Unblock direct receivers when the receive loop terminates."""
        while self._recv_waiters:
            waiter = self._recv_waiters.popleft()

            if not waiter.done():
                if self._receive_error is None:
                    waiter.set_result(None)
                else:
                    waiter.set_exception(self._receive_error)

    async def _disconnect(self, *, close_socket: bool) -> None:
        """Close the native socket and release the connection reservation."""
        ws, self._ws = self._ws, None
        task, self._recv_task = self._recv_task, None
        self._last_message = None
        self._receive_error = None

        self._finish_receivers()

        try:
            await self._heartbeat.pause()
        finally:
            try:
                if close_socket and ws is not None:
                    await ws.close()
            finally:
                try:
                    if task is not None:
                        await _cancel_and_wait(task)
                finally:
                    await self._events.close()

    async def _receive_loop(self, ws: wreq.WebSocket) -> None:
        """Read native messages until shutdown while preserving timeout semantics."""
        try:
            while self._ws is ws:
                try:
                    # wreq 0.12 queues sends and close behind the current native read.
                    message = await ws.recv(timeout=_READ_TIMEOUT)
                except wreq.exceptions.TimeoutError:
                    continue
                except Exception as exc:
                    if self._ws is not ws:
                        return

                    self._receive_error = exc

                    self._logger.error("WebSocket receive failed", error_type=type(exc).__name__)
                    self._events.dispatch("error", exc)

                    return

                if message is None:
                    self._events.dispatch("close")

                    return

                # Deliver the raw message before applying the event prehook.
                self._deliver_message(message)

                if self._data_prehook is not None:
                    try:
                        message = self._data_prehook(message)
                    except Exception as exc:
                        self._events.dispatch("error", exc)

                        continue

                self._last_message = message

                self._events.dispatch("message", message)
        finally:
            if self._ws is ws:
                self._ws = None
                self._last_message = None

                await self._heartbeat.pause()

            self._finish_receivers()
