from __future__ import annotations

import asyncio
import contextlib
from datetime import timedelta
from typing import (
    TYPE_CHECKING,
    Any,
    AsyncIterator,
    Callable,
    TypeAlias,
    Coroutine,
    Final,
)

import wreq
from v2.types import DefaultLogger
from v2.datastruct import EventDispatcher

if TYPE_CHECKING:
    from typing import Unpack
    from v2.connection.http import HTTPClient
    from v2.types import LoggerProtocol

__all__: tuple[str, ...] = ("WebSocketClient",)

CoroFunc: TypeAlias = Callable[..., Coroutine[Any, Any, Any]]

_DEFAULT_PING_MESSAGE: Final[str] = '{"type":"ping"}'
_DEFAULT_PING_INTERVAL: Final[float] = 60.0


class _HeartbeatManager:
    __slots__: tuple[str, ...] = (
        "_sender",
        "_dispatcher",
        "_logger",
        "_task",
    )

    def __init__(
        self,
        sender: Callable[[wreq.Message], Coroutine[Any, Any, None]],
        dispatcher: EventDispatcher,
        logger: LoggerProtocol,
    ) -> None:
        self._sender = sender
        self._dispatcher = dispatcher
        self._logger = logger
        self._task: asyncio.Task[None] | None = None

    def start(self, interval: float, message: wreq.Message) -> None:
        self.stop()
        self._task = asyncio.create_task(self._loop(interval, message), name="ws-ping")

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None

    async def _loop(self, interval: float, message: wreq.Message) -> None:
        try:
            while True:
                await asyncio.sleep(interval)
                await self._sender(message)
                self._logger.debug("Ping sent", payload=message)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._dispatcher.dispatch("error", exc)


class WebSocketClient:
    __slots__: tuple[str, ...] = (
        "_client",
        "_logger",
        "_ws",
        "_recv_task",
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
        self._client: wreq.Client = http_client.wclient
        self._logger = logger
        self._data_prehook = data_prehook
        self._events = EventDispatcher(logger)
        self._heartbeat = _HeartbeatManager(self.send, self._events, logger)

        self._ws: wreq.WebSocket | None = None
        self._recv_task: asyncio.Task[None] | None = None
        self._last_message: wreq.Message | None = None

    async def __aenter__(self) -> WebSocketClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await asyncio.to_thread(self._client.close)
        if self._ws is not None:
            await self._ws.close()

    @property
    def is_connected(self) -> bool:
        return self._ws is not None

    @property
    def last_message(self) -> wreq.Message | None:
        return self._last_message

    def _add_listener(self, func: CoroFunc, name: str | None = None) -> None:
        self._events.register(func, name)

    def _remove_listener(self, func: CoroFunc, name: str | None = None) -> None:
        self._events.unregister(func, name)

    def event(self, name: str | None = None, /) -> Callable[[CoroFunc], CoroFunc]:
        def decorator(coro: CoroFunc) -> CoroFunc:
            self._add_listener(coro, name)
            return coro

        return decorator

    @contextlib.asynccontextmanager
    async def connect(
        self,
        url: str,
        **kwargs: Unpack[wreq.WebSocketRequest],
    ) -> AsyncIterator[WebSocketClient]:
        ws: wreq.WebSocket = await self._client.websocket(url, **kwargs)
        async with ws:
            self._ws = ws
            self._recv_task = asyncio.create_task(
                self._receive_loop(), name=f"ws-recv:{url}"
            )
            try:
                self._events.dispatch("open")
                yield self
            finally:
                self._heartbeat.stop()
                self._recv_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._recv_task
                self._ws = None
                self._recv_task = None
                self._last_message = None

    async def recv(self, *, timeout: float | None = None) -> wreq.Message | None:
        delta = timedelta(seconds=timeout) if timeout is not None else None
        return await self._require_ws().recv(timeout=delta)

    async def send(self, message: wreq.Message) -> None:
        await self._require_ws().send(message)

    def start_pinging(
        self,
        interval: float = _DEFAULT_PING_INTERVAL,
        ping_message: wreq.Message | None = None,
    ) -> None:
        msg = ping_message or wreq.Message.from_text(_DEFAULT_PING_MESSAGE)
        self._heartbeat.start(interval, msg)

    def stop_pinging(self) -> None:
        self._heartbeat.stop()

    def _require_ws(self) -> wreq.WebSocket:
        if self._ws is None:
            raise RuntimeError("WebSocket is not currently connected")
        return self._ws

    async def _receive_loop(self) -> None:
        ws = self._require_ws()
        try:
            while True:
                try:
                    message = await ws.recv(timeout=None)
                except Exception as exc:
                    self._events.dispatch("error", exc)
                    break

                if message is None:
                    self._events.dispatch("close")
                    break

                if self._data_prehook is not None:
                    message = self._data_prehook(message)

                self._last_message = message
                self._events.dispatch("message", message)
        except asyncio.CancelledError:
            pass
