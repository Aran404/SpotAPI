"""WebSocket connection, heartbeat, receive and listener ownership contracts."""

from __future__ import annotations

import asyncio
from typing import Any, Self
from unittest.mock import AsyncMock, Mock

import pytest
import wreq

from spotapi.v2.connection.http import HTTPClient
from spotapi.v2.connection.websocket import WebSocketClient


class Socket:
    def __init__(self) -> None:
        self.incoming: asyncio.Queue[wreq.Message | Exception | None] = asyncio.Queue()
        self.sent: asyncio.Queue[wreq.Message] = asyncio.Queue()
        self.closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    async def recv(self, **kwargs: Any) -> wreq.Message | None:
        item = await self.incoming.get()

        if isinstance(item, Exception):
            raise item

        return item

    async def send(self, message: wreq.Message) -> None:
        await self.sent.put(message)

    async def close(self) -> None:
        self.closed = True


def make_client(*sockets: Socket) -> WebSocketClient:
    remaining = iter(sockets)

    async def websocket(*args: object, **kwargs: Any) -> Socket:
        return next(remaining)

    http = Mock(spec=HTTPClient)
    http.wclient.websocket = AsyncMock(side_effect=websocket)

    return WebSocketClient(http_client=http)


async def test_heartbeat_restarts_on_next_connection() -> None:
    first, second = Socket(), Socket()
    client = make_client(first, second)

    client.start_pinging(interval=0.001)

    async with client.connect("wss://example.test"):
        await asyncio.wait_for(first.sent.get(), 1)

    assert first.closed
    assert client._heartbeat._task is None

    async with client.connect("wss://example.test"):
        await asyncio.wait_for(second.sent.get(), 1)

    assert second.closed
    assert client._heartbeat._task is None
    assert not client._heartbeat._stopping


async def test_recv_timeout_does_not_consume_next_message() -> None:
    socket = Socket()
    client = make_client(socket)

    async with client.connect("wss://example.test"):
        with pytest.raises(wreq.exceptions.TimeoutError):
            await client.recv(timeout=0.001)

        receiver = asyncio.create_task(client.recv())

        await asyncio.sleep(0)

        message = wreq.Message.from_text("hello")

        await socket.incoming.put(message)

        assert await asyncio.wait_for(receiver, 1) is message
        assert not client._recv_waiters


async def test_remote_close_stops_heartbeat_and_wakes_receiver() -> None:
    socket = Socket()
    client = make_client(socket)

    client.start_pinging(interval=0.001)

    async with client.connect("wss://example.test"):
        receiver = asyncio.create_task(client.recv())

        await asyncio.sleep(0)
        await socket.incoming.put(None)

        assert await asyncio.wait_for(receiver, 1) is None
        assert not client.is_connected
        assert client._heartbeat._task is None


async def test_context_exit_cancels_slow_listeners() -> None:
    socket = Socket()
    client = make_client(socket)
    started, stopped = asyncio.Event(), asyncio.Event()

    @client.event("message")
    async def on_message(message: wreq.Message) -> None:
        started.set()

        try:
            await asyncio.Future()
        finally:
            stopped.set()

    async with client.connect("wss://example.test"):
        await socket.incoming.put(wreq.Message.from_text("hello"))
        await asyncio.wait_for(started.wait(), 1)

    assert stopped.is_set()
    assert not client._events._tasks


async def test_connection_failure_releases_reservation() -> None:
    calls = 0
    socket = Socket()

    async def connect(*args: object, **kwargs: Any) -> Socket:
        nonlocal calls
        calls += 1

        if calls == 1:
            raise wreq.exceptions.ConnectionError("failed")

        return socket

    http = Mock(spec=HTTPClient)
    http.wclient.websocket = AsyncMock(side_effect=connect)
    client = WebSocketClient(http_client=http)

    with pytest.raises(wreq.exceptions.ConnectionError):
        async with client.connect("wss://example.test"):
            pass

    async with client.connect("wss://example.test"):
        assert client.is_connected

    assert socket.closed


async def test_cancelled_context_closes_socket() -> None:
    socket = Socket()
    client = make_client(socket)
    started = asyncio.Event()

    async def run() -> None:
        async with client.connect("wss://example.test"):
            started.set()
            await asyncio.Future()

    task = asyncio.create_task(run())

    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert socket.closed
    assert client._recv_task is None


async def test_cleanup_failure_preserves_body_cancellation() -> None:
    class BrokenClose(Socket):
        async def close(self) -> None:
            raise ValueError("socket close failed")

    client = make_client(BrokenClose())

    with pytest.raises(asyncio.CancelledError) as raised:
        async with client.connect("wss://example.test"):
            raise asyncio.CancelledError()

    assert isinstance(raised.value.__cause__, ValueError)
