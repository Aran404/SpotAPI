"""Exercise native wreq command scheduling against a silent local WebSocket."""

from __future__ import annotations

import asyncio
import base64
import hashlib
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import wreq

from spotapi.connection import HTTPClient, WebSocketClient


@asynccontextmanager
async def silent_server() -> AsyncGenerator[tuple[str, asyncio.Future[bytes]], None]:
    received: asyncio.Future[bytes] = asyncio.get_running_loop().create_future()
    clients: set[asyncio.Task[None]] = set()

    async def connection(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        task = asyncio.current_task()

        if task is not None:
            clients.add(task)

        try:
            request = await reader.readuntil(b"\r\n\r\n")
            key = next(
                line.split(b":", 1)[1].strip()
                for line in request.splitlines()
                if line.lower().startswith(b"sec-websocket-key:")
            )
            digest = hashlib.sha1(
                key + b"258EAFA5-E914-47DA-95CA-C5AB0DC85B11", usedforsecurity=False
            ).digest()
            accept = base64.b64encode(digest)

            writer.write(
                b"HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\n"
                b"Connection: Upgrade\r\nSec-WebSocket-Accept: " + accept + b"\r\n\r\n"
            )
            await writer.drain()

            while True:
                header = await reader.readexactly(2)
                opcode, length = header[0] & 15, header[1] & 127

                if length == 126:
                    length = int.from_bytes(await reader.readexactly(2), "big")
                elif length == 127:
                    length = int.from_bytes(await reader.readexactly(8), "big")

                mask = await reader.readexactly(4) if header[1] & 128 else b""
                payload = await reader.readexactly(length)

                if mask:
                    payload = bytes(value ^ mask[index % 4] for index, value in enumerate(payload))

                if opcode == 8:
                    writer.write(b"\x88\x00")
                    await writer.drain()

                    return

                if opcode == 1 and not received.done():
                    received.set_result(payload)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            await writer.wait_closed()

            if task is not None:
                clients.discard(task)

    server = await asyncio.start_server(connection, "127.0.0.1", 0)
    address = server.sockets[0].getsockname()

    try:
        async with server:
            yield f"ws://127.0.0.1:{address[1]}", received
    finally:
        for task in clients:
            task.cancel()

        await asyncio.gather(*clients, return_exceptions=True)


async def test_native_idle_reader_does_not_block_send_or_close() -> None:
    async with silent_server() as (url, received), HTTPClient() as http:
        websocket = WebSocketClient(http_client=http)

        async with asyncio.timeout(5), websocket.connect(url):
            await asyncio.sleep(0)
            await websocket.send(wreq.Message.from_text("hello"))

            assert await received == b"hello"


async def test_explicit_native_close_is_safe_inside_connection_context() -> None:
    async with silent_server() as (url, _received), HTTPClient() as http:
        websocket = WebSocketClient(http_client=http)

        async with asyncio.timeout(5), websocket.connect(url):
            await asyncio.sleep(0)
            await websocket.close()

            assert not websocket.is_connected
