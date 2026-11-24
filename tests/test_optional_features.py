"""Ownership, bounded transfers and explicit optional integrations."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

import spotapi.media as media_module
import spotapi.sync as sync_module
from spotapi import Media, SavedSession, SyncCatalogue
from spotapi.catalogue import Catalogue
from spotapi.embeds import Embed, get_embed
from spotapi.login import SessionInfo
from spotapi.models import TrackDetails
from spotapi.resources import parse_spotify_resource
from spotapi.serialization import to_dict
from spotapi.types import BaseClientError


def asset() -> Embed:
    return Embed(
        parse_spotify_resource("spotify:track:abc"),
        "Track",
        None,
        "https://p.scdn.co/preview.mp3",
        ("https://i.scdn.co/image/abc",),
    )


async def test_embed_preserves_proxy_and_closes_before_rejecting_invalid_html(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.get = AsyncMock(return_value=SimpleNamespace(text="<html></html>"))
    factory = Mock(return_value=client)
    monkeypatch.setattr("spotapi.embeds.AsyncClient", factory)

    with pytest.raises(BaseClientError):
        await get_embed("spotify:track:abc", proxy="http://proxy.test:8080")

    factory.assert_called_once_with(proxy="http://proxy.test:8080")
    client.__aexit__.assert_awaited_once()


def install_transfer(
    monkeypatch: pytest.MonkeyPatch, chunks: list[bytes], *, content_type: str = "image/jpeg"
) -> MagicMock:
    async def stream_bytes() -> AsyncGenerator[bytes, None]:
        for chunk in chunks:
            yield chunk

    @asynccontextmanager
    async def byte_context() -> AsyncGenerator[AsyncGenerator[bytes, None], None]:
        try:
            yield stream_bytes()
        finally:
            http.stream_closed = True

    response = Mock(
        status=Mock(is_success=Mock(return_value=True)),
        headers=[(b"content-type", content_type.encode())],
        content_length=None,
        stream=byte_context,
    )

    @asynccontextmanager
    async def stream(*args: Any, **kwargs: Any) -> AsyncGenerator[Mock, None]:
        assert "authorization" not in kwargs.get("headers", {})
        yield response

    http = MagicMock()
    http.stream_closed = False
    http.__aenter__ = AsyncMock(return_value=http)
    http.__aexit__ = AsyncMock(return_value=False)
    http.stream = stream
    monkeypatch.setattr(media_module, "HTTPClient", lambda: http)
    return http


async def test_media_bounds_chunked_responses_before_creating_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    http = install_transfer(monkeypatch, [b"ab", b"cd"])
    path = tmp_path / "cover.jpg"
    with pytest.raises(BaseClientError, match="max_bytes"):
        await Media(max_bytes=3).download_cover(asset(), path)
    assert not path.exists()
    http.__aexit__.assert_awaited_once()
    assert http.stream_closed is True


async def test_media_download_does_not_replace_an_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_transfer(monkeypatch, [b"data"])
    path = tmp_path / "cover.jpg"
    path.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        await Media().download_cover(asset(), path)
    assert path.read_bytes() == b"original"


async def test_cancelled_download_does_not_publish_the_staged_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_transfer(monkeypatch, [b"data"])
    started = asyncio.Event()
    release = Event()
    loop = asyncio.get_running_loop()
    original_write = Path.write_bytes

    def paused_write(path: Path, data: bytes) -> int:
        loop.call_soon_threadsafe(started.set)
        if not release.wait(timeout=5):
            raise TimeoutError("Test did not release the staged write")
        return original_write(path, data)

    monkeypatch.setattr(Path, "write_bytes", paused_write)
    destination = tmp_path / "cover.jpg"
    download = asyncio.create_task(Media().download_cover(asset(), destination))
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        download.cancel()
        await asyncio.sleep(0)
        assert not destination.exists()
    finally:
        release.set()

    with pytest.raises(asyncio.CancelledError):
        await download

    assert list(tmp_path.iterdir()) == []


async def test_media_rejects_wrong_content_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    install_transfer(monkeypatch, [b"html"], content_type="text/html")
    with pytest.raises(BaseClientError, match="media type"):
        await Media().download_cover(asset(), tmp_path / "cover.jpg")


@pytest.mark.parametrize(
    "url",
    [
        "http://i.scdn.co/x",
        "https://example.com/x",
        "https://i.scdn.co.evil.test/x",
        "https://user:password@i.scdn.co/x",
    ],
)
def test_media_rejects_untrusted_or_credentialed_urls(url: str) -> None:
    with pytest.raises(ValueError):
        media_module._media_url(url)


def test_saved_session_metadata_never_contains_the_cookie(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = Mock(get_password=Mock(return_value="raw-test-cookie"))

    def backend_for(self: SavedSession) -> Mock:
        return backend

    monkeypatch.setattr(SavedSession, "_backend", backend_for)
    saved = SavedSession("test")
    assert saved.info() == SessionInfo("test", True)
    assert "raw-test-cookie" not in repr(saved)
    assert "raw-test-cookie" not in str(to_dict(saved.info()))
    saved.save("new-test-cookie")
    backend.set_password.assert_called_once_with("spotapi", "test", "new-test-cookie")
    saved.clear()
    backend.delete_password.assert_called_once_with("spotapi", "test")


def test_sync_catalogue_reuses_and_closes_one_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = Mock(spec=Catalogue)
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.close = AsyncMock()
    expected = Mock(spec=TrackDetails)
    fake.get_track = AsyncMock(return_value=expected)

    def catalogue_for(**kwargs: Any) -> Mock:
        return fake

    monkeypatch.setattr(sync_module, "Catalogue", catalogue_for)
    with SyncCatalogue() as spotify:
        assert spotify.get_track("first") is expected
        assert spotify.get_track("second") is expected
    fake.__aenter__.assert_awaited_once()
    fake.close.assert_awaited_once()
    with pytest.raises(RuntimeError, match="with SyncCatalogue"):
        spotify.get_track("after-close")


async def test_sync_catalogue_rejects_nested_event_loop_use() -> None:
    with pytest.raises(RuntimeError, match="async Catalogue"), SyncCatalogue():
        pass


def test_sync_close_rejects_nested_loop_without_losing_ownership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = Mock(spec=Catalogue)
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.close = AsyncMock()
    expected = Mock(spec=TrackDetails)
    fake.get_track = AsyncMock(return_value=expected)

    def catalogue_for(**kwargs: Any) -> Mock:
        return fake

    monkeypatch.setattr(sync_module, "Catalogue", catalogue_for)

    async def close_inside_loop(spotify: SyncCatalogue) -> None:
        with pytest.raises(RuntimeError, match="async Catalogue"):
            spotify.close()
        fake.close.assert_not_called()

    with SyncCatalogue() as spotify:
        asyncio.run(close_inside_loop(spotify))
        assert spotify.get_track("still-open") is expected
    fake.close.assert_awaited_once()


def test_mcp_only_registers_read_tools_without_loading_optional_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spotapi.mcp import build_server

    class Server:
        def __init__(self, name: str) -> None:
            self.tools: dict[str, Any] = {}

        def tool(self) -> Any:
            def register(function: Any) -> Any:
                self.tools[function.__name__] = function
                return function

            return register

        def resource(self, template: str) -> Any:
            def register(function: Any) -> Any:
                return function

            return register

    def import_sdk(name: str) -> SimpleNamespace:
        return SimpleNamespace(FastMCP=Server)

    monkeypatch.setattr("spotapi.mcp.importlib.import_module", import_sdk)
    server = build_server()
    assert "get_resource" in server.tools and "get_track_visuals" in server.tools
    assert "captions" not in server.tools
    assert not set(server.tools) & {"delete", "download", "play", "follow", "logout"}
    assert "captions" in build_server(cookie="test-cookie").tools


def test_sync_page_iteration_closes_an_early_stopped_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spotapi.models import AlbumTrack

    closed = False

    async def pages(
        value: str, *, limit: int = 50
    ) -> AsyncGenerator[tuple[AlbumTrack, ...], None]:
        nonlocal closed
        try:
            yield ()
            yield ()
        finally:
            closed = True

    fake = Mock(spec=Catalogue)
    fake.__aenter__ = AsyncMock(return_value=fake)
    fake.close = AsyncMock()
    fake.get_album_tracks = pages

    def factory(**kwargs: Any) -> Mock:
        return fake

    monkeypatch.setattr(sync_module, "Catalogue", factory)
    with SyncCatalogue() as spotify:
        stream = spotify.get_album_tracks("album")
        assert next(stream) == ()
        stream.close()
        assert closed


async def test_streaming_requests_publish_retry_after_without_replaying() -> None:
    from spotapi.connection import HTTPClient

    response = MagicMock()
    response.status.as_int.return_value = 429
    response.headers = [(b"retry-after", b"5")]
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)
    client = HTTPClient.__new__(HTTPClient)
    client._wclient = Mock(request=AsyncMock(return_value=response))
    client._rate_limiter = Mock(wait=AsyncMock())
    async with client.stream("GET", "https://cdn.example/asset") as received:
        assert received is response
    client._rate_limiter.pause.assert_called_once_with("cdn.example", 5.0)
    client._wclient.request.assert_awaited_once()
    response.__aexit__.assert_awaited_once()


async def test_mcp_player_tools_require_opt_in_and_declare_mutations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("mcp")
    from spotapi.mcp import build_server

    ordinary = build_server(cookie="synthetic-cookie")
    assert "pause" not in {tool.name for tool in await ordinary.list_tools()}

    with pytest.raises(ValueError, match="cookie"):
        build_server(allow_player=True)

    player = Mock(
        state=None,
        devices=(),
        current_track_details=AsyncMock(return_value=None),
        next=AsyncMock(),
        pause=AsyncMock(),
        resume=AsyncMock(),
        like=AsyncMock(),
        transfer=AsyncMock(),
    )
    closed: list[bool] = []

    @asynccontextmanager
    async def scope(cookie: str) -> AsyncGenerator[Mock, None]:
        assert cookie == "synthetic-cookie"
        try:
            yield player
        finally:
            closed.append(True)

    monkeypatch.setattr("spotapi.mcp._player_session", scope)
    server = build_server(cookie="synthetic-cookie", allow_player=True)
    tools = {tool.name: tool for tool in await server.list_tools()}
    assert tools["now_playing"].annotations is not None
    assert tools["now_playing"].annotations.readOnlyHint is True

    arguments = {
        "now_playing": {},
        "pause": {},
        "resume": {},
        "next": {},
        "like": {},
        "transfer": {"device_id": "phone", "play": False},
    }
    for name, values in arguments.items():
        if name != "now_playing":
            assert tools[name].annotations is not None
            assert tools[name].annotations.readOnlyHint is False
        await server.call_tool(name, values)

    player.like.assert_awaited_once_with()
    player.transfer.assert_awaited_once_with("phone", play=False)
    player.next.assert_awaited_once()
    assert len(closed) == len(arguments)

    player.pause.side_effect = RuntimeError("device disconnected")
    with pytest.raises(Exception, match="device disconnected"):
        await server.call_tool("pause", {})
    assert len(closed) == len(arguments) + 1


async def test_mcp_reports_when_cleanup_fails_after_an_operation_completed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spotapi.mcp import _player_session

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    player = Mock()

    @asynccontextmanager
    async def connection() -> AsyncGenerator[Mock, None]:
        try:
            yield player
        finally:
            raise ConnectionError("cleanup unavailable")

    monkeypatch.setattr("spotapi.mcp.AsyncClient.from_cookies", AsyncMock(return_value=client))
    monkeypatch.setattr("spotapi.mcp.Player", Mock(return_value=Mock(connect=connection)))

    with pytest.raises(RuntimeError, match="operation completed") as caught:
        async with _player_session("synthetic-cookie") as active:
            assert active is player

    assert isinstance(caught.value.__cause__, ConnectionError)
    client.__aexit__.assert_awaited_once()


async def test_mcp_can_like_a_supplied_track_without_a_player(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("mcp")
    from spotapi.mcp import build_server

    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    login = AsyncMock(return_value=client)
    add = AsyncMock()
    connect = Mock(side_effect=AssertionError("A supplied track does not need a player"))
    monkeypatch.setattr("spotapi.mcp.AsyncClient.from_cookies", login)
    monkeypatch.setattr("spotapi.mcp.Player", connect)
    monkeypatch.setattr("spotapi.mcp.LikedTracks", Mock(return_value=Mock(add=add)))
    server = build_server(cookie="synthetic-cookie", allow_player=True)

    await server.call_tool("like", {"track": "spotify:track:test"})
    add.assert_awaited_once_with(["spotify:track:test"])
    client.__aexit__.assert_awaited_once()
    connect.assert_not_called()

    login.reset_mock()
    with pytest.raises(Exception, match="open.spotify.com"):
        await server.call_tool("like", {"track": "https://example.com/track/test"})
    login.assert_not_awaited()


async def test_mcp_public_reads_and_batch_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("mcp")
    from spotapi.mcp import build_server
    from spotapi.public import Public

    lookup = AsyncMock(return_value={"name": "Example"})
    search = AsyncMock(return_value={"tracks": []})
    fetch = AsyncMock(return_value=())
    monkeypatch.setattr(Public, "get", lookup)
    monkeypatch.setattr(Public, "search", search)
    monkeypatch.setattr(Public, "fetch_many", fetch)
    server = build_server()

    await server.call_tool("get_resource", {"value": "spotify:track:abc"})
    lookup.assert_awaited_once_with("spotify:track:abc")
    await server.call_tool("search", {"query": "Example", "limit": 3})
    search.assert_awaited_once_with("Example", types=("track", "artist"), limit=3)
    await server.call_tool("batch", {"values": ["spotify:track:abc"], "concurrency": 2})
    fetch.assert_awaited_once_with(["spotify:track:abc"], concurrency=2)
    fetch.reset_mock()
    with pytest.raises(Exception, match="at most 50"):
        await server.call_tool("batch", {"values": ["spotify:track:abc"] * 51})
    fetch.assert_not_awaited()


async def test_mcp_playlist_read_closes_stream_and_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("mcp")
    from spotapi.mcp import build_server

    closed: list[bool] = []

    async def pages(value: str, *, limit: int) -> AsyncGenerator[tuple[dict[str, str], ...], None]:
        assert value == "playlist" and limit == 2
        try:
            yield ({"uid": "one"}, {"uid": "two"})
            raise AssertionError("Only the first page should be read")
        finally:
            closed.append(True)

    catalogue = MagicMock()
    catalogue.__aenter__ = AsyncMock(return_value=catalogue)
    catalogue.__aexit__ = AsyncMock(return_value=False)
    catalogue.get_playlist_items = pages
    monkeypatch.setattr("spotapi.mcp.Catalogue", Mock(return_value=catalogue))
    await build_server().call_tool("playlist_items", {"value": "playlist", "limit": 2})
    assert closed == [True]
    catalogue.__aexit__.assert_awaited_once()
