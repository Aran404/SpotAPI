"""Offline tests for Connect commands; no Spotify service or terminal needed."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypeVar, cast
from unittest.mock import AsyncMock

import pytest

from spotapi._connect.commands import Command, duration_ms, parse_command, profile_name
from spotapi._connect.session import execute

Callback = TypeVar("Callback", bound=Callable[..., object])

if TYPE_CHECKING:
    from spotapi import AsyncClient, Catalogue, Player
    from spotapi.models.catalogue.track import Track


def as_player(stub: StubPlayer) -> Player:
    """Adapt a deliberately partial fake at the test boundary."""
    return cast("Player", stub)


def as_catalogue(stub: SimpleNamespace) -> Catalogue:
    return cast("Catalogue", stub)


@pytest.mark.parametrize(
    ("input_text", "expected"),
    [
        ("/next", Command("next")),
        ("prev", Command("previous")),
        ("/search 'Daft Punk'", Command("search", "Daft Punk")),
        ("/seek 1:30", Command("seek", "1:30")),
        ("/queue 2", Command("queue", "2")),
    ],
)
def test_parse_command(input_text: str, expected: Command) -> None:
    assert parse_command(input_text) == expected


@pytest.mark.parametrize("value", ["", "../unsafe", "has space", "@user", "a" * 41])
def test_profile_rejects_invalid_name(value: str) -> None:
    with pytest.raises(ValueError):
        profile_name(value)


def test_parse_seconds_and_format() -> None:
    assert duration_ms("90") == 90_000
    assert duration_ms("1:30") == 90_000
    assert duration_ms("1:02:03") == 3_723_000
    for value in ("1:77", "-2", "abc", "24:00:01"):
        with pytest.raises(ValueError):
            duration_ms(value)


@pytest.mark.parametrize(
    "value", ["next 2", "seek", "use 0", "shuffle yes", "volume 101", "unknown"]
)
def test_bad_commands_have_errors(value: str) -> None:
    with pytest.raises(ValueError):
        parse_command(value)


@dataclass
class Device:
    id: str
    name: str
    type: str = "Computer"


class StubPlayer:
    def __init__(self) -> None:
        self.is_ready = True
        self.devices = (Device("a", "Desktop"), Device("b", "Browser"))
        self.target_device_id: str | None = None
        self.state = SimpleNamespace(active_device_id="a", is_paused=False)
        self.next = AsyncMock()
        self.previous = AsyncMock()
        self.pause = AsyncMock()
        self.resume = AsyncMock()
        self.transfer = AsyncMock()
        self.add_to_queue = AsyncMock()
        self.play = AsyncMock()
        self.seek = AsyncMock()
        self.refresh = AsyncMock()
        self.volume = AsyncMock()
        self.shuffle = AsyncMock()
        self.repeat = AsyncMock()

    def select(self, device: Device) -> None:
        self.target_device_id = device.id




@pytest.mark.parametrize(
    "source",
    [
        "help", "devices", "pause", "resume", "toggle", "next", "previous",
        "refresh", "quit", "search The Weeknd", "play 1", "queue 3",
        "transfer 1", "use 2", "volume 60", "shuffle on", "shuffle off",
        "repeat context", "repeat off", "repeat track", "seek 1:30",
    ],
)
def test_all_documented_commands_parse(source: str) -> None:
    """A valid no-argument command must never fall through a match statement."""
    assert parse_command(source).action


@pytest.mark.asyncio
async def test_commands_reach_player_after_validation() -> None:
    player = StubPlayer()
    catalogue = as_catalogue(SimpleNamespace())
    for source in ("pause", "resume", "next", "previous", "volume 35", "shuffle on", "repeat off"):
        await execute(parse_command(source), player=as_player(player), catalogue=catalogue)
    player.pause.assert_awaited_once()
    player.resume.assert_awaited_once()
    player.next.assert_awaited_once()
    player.previous.assert_awaited_once()
    player.volume.assert_awaited_once_with(35)
    player.shuffle.assert_awaited_once_with(True)
    player.repeat.assert_awaited_once_with("off")


@pytest.mark.asyncio
async def test_help_does_not_require_connection() -> None:
    player = StubPlayer()
    player.is_ready = False
    outcome = await execute(
        parse_command("help"), player=as_player(player), catalogue=as_catalogue(SimpleNamespace())
    )
    assert "Ctrl+K" in outcome.message


@pytest.mark.asyncio
async def test_target_is_not_transfer() -> None:
    player = StubPlayer()
    catalogue = SimpleNamespace()
    result = await execute(
        Command("use", "2"), player=as_player(player), catalogue=as_catalogue(catalogue)
    )
    assert player.target_device_id == "b"
    player.transfer.assert_not_awaited()
    assert "not transferred" in result.message
    await execute(
        Command("transfer", "2"), player=as_player(player), catalogue=as_catalogue(catalogue)
    )
    player.transfer.assert_awaited_once_with(player.devices[1])


@pytest.mark.asyncio
async def test_ambiguous_command_failure_is_not_retried() -> None:
    player = StubPlayer()
    player.next.side_effect = TimeoutError()
    with pytest.raises(TimeoutError):
        await execute(
            Command("next"), player=as_player(player), catalogue=as_catalogue(SimpleNamespace())
        )
    player.next.assert_awaited_once()


@pytest.mark.asyncio
async def test_seek_and_search_result_actions() -> None:
    player = StubPlayer()
    hits = (SimpleNamespace(name="One More Time", uri="spotify:track:one"),)
    catalogue = SimpleNamespace(search=AsyncMock(return_value=SimpleNamespace(tracks=hits)))
    result = await execute(
        Command("search", "Daft Punk"), player=as_player(player), catalogue=as_catalogue(catalogue)
    )
    assert result.search_hits == hits
    await execute(
        Command("queue", "1"),
        player=as_player(player),
        catalogue=as_catalogue(catalogue),
        hits=cast("tuple[Track, ...]", hits),
    )
    player.add_to_queue.assert_awaited_once_with("spotify:track:one")
    await execute(
        Command("seek", "1:30"), player=as_player(player), catalogue=as_catalogue(catalogue)
    )
    player.seek.assert_awaited_once_with(90_000)


@pytest.mark.asyncio
async def test_disconnected_mutations_do_not_run() -> None:
    player = StubPlayer()
    player.is_ready = False
    with pytest.raises(RuntimeError, match="Connecting"):
        await execute(
            Command("pause"), player=as_player(player), catalogue=as_catalogue(SimpleNamespace())
        )
    player.pause.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_auth_uses_shell_cookie_without_force(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spotapi

    from spotapi._connect.auth import open_account

    fake_client = SimpleNamespace(from_cookies=AsyncMock(return_value="session"))
    monkeypatch.setenv("SPOTIFY_COOKIE", "sp_dc=private")
    monkeypatch.setitem(spotapi.__dict__, "AsyncClient", fake_client)
    assert await open_account("default", force=False) == "session"
    fake_client.from_cookies.assert_awaited_once_with("sp_dc=private")


@pytest.mark.asyncio
async def test_connect_auth_force_uses_fresh_named_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import spotapi

    from spotapi._connect.auth import open_account

    class FakeSavedSession:
        def __init__(self, name: str) -> None:
            self.name = name

    browser = AsyncMock(return_value="fresh")
    monkeypatch.setitem(spotapi.__dict__, "AsyncClient", SimpleNamespace())
    monkeypatch.setenv("SPOTIFY_COOKIE", "sp_dc=old")
    monkeypatch.setitem(spotapi.__dict__, "SavedSession", FakeSavedSession)
    monkeypatch.setitem(spotapi.__dict__, "browser_login", browser)
    assert await open_account("work", force=True) == "fresh"
    call = browser.await_args
    assert call is not None
    assert call.kwargs["saved"].name == "work"
    assert call.kwargs["force"] is True


@pytest.mark.asyncio
async def test_connect_ui_mounts_and_exits_in_headless_terminal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Optional Textual smoke test; runs when the Connect extra is installed."""
    pytest.importorskip("textual")
    from spotapi._connect import app as connect_ui
    from textual.widgets import Input

    class FakeCatalogue:
        def __init__(self, client: object) -> None:
            self.client = client

        async def __aenter__(self) -> FakeCatalogue:
            return self

        async def close(self) -> None:
            return None

    class FakePlayer:
        state = None
        devices: tuple[()] = ()
        target_device_id = None
        is_ready = False

        def __init__(self, client: object, *, name: str) -> None:
            self.client = client
            self.name = name

        def listen(self, name: str) -> Callable[[Callback], Callback]:
            def register(callback: Callback) -> Callback:
                return callback

            return register

        async def start(self) -> None:
            await asyncio.Event().wait()

        async def close(self) -> None:
            return None

    monkeypatch.setattr(connect_ui, "Catalogue", FakeCatalogue)
    monkeypatch.setattr(connect_ui, "Player", FakePlayer)
    application = connect_ui.ConnectApp(cast("AsyncClient", SimpleNamespace()))
    async with application.run_test(size=(110, 32)) as pilot:
        await pilot.pause()
        assert application.query_one("#command", Input).placeholder


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("clear", "clear"),
        ("/cls", "clear"),
        ("exit", "quit"),
        ("exit()", "quit"),
        ("/quit", "quit"),
    ],
)
def test_shell_conveniences(source: str, expected: str) -> None:
    assert parse_command(source) == Command(expected)


@pytest.mark.asyncio
async def test_search_requests_twenty_results_not_five() -> None:
    player = StubPlayer()
    catalogue = SimpleNamespace(search=AsyncMock(return_value=SimpleNamespace(tracks=())))
    await execute(
        Command("search", "Radiohead"),
        player=as_player(player),
        catalogue=as_catalogue(catalogue),
    )
    catalogue.search.assert_awaited_once_with("Radiohead", types="track", limit=20)


@pytest.mark.asyncio
async def test_clear_and_quit_do_not_mutate_spotify() -> None:
    player = StubPlayer()
    player.is_ready = False
    for source in ("clear", "cls", "exit", "exit()"):
        result = await execute(
            parse_command(source),
            player=as_player(player),
            catalogue=as_catalogue(SimpleNamespace()),
        )
        assert result.message
    player.next.assert_not_awaited()
    player.pause.assert_not_awaited()
