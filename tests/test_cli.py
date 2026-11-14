"""Exercise command output and failure status without network access."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import (
    AsyncClient,
    AuthSession,
    Playlist,
    Private,
    Public,
    SearchResults,
    SpotAPIError,
)
from spotapi.cli import main


def test_cli_get_outputs_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    resource = Public.parse_url("spotify:track:abc")
    monkeypatch.setattr(Public, "get", AsyncMock(return_value=resource))

    assert main(["get", resource.uri]) == 0
    assert json.loads(capsys.readouterr().out)["uri"] == resource.uri


def test_cli_reports_the_installed_version(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("spotapi.cli.package_version", Mock(return_value="2.1.0"))

    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])

    assert exit_info.value.code == 0
    assert capsys.readouterr().out == "spotapi 2.1.0\n"


def test_cli_discover_explains_the_optional_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=None))
    launch = Mock()
    monkeypatch.setattr("spotapi.cli.importlib.import_module", launch)
    assert main(["discover", "Daft Punk"]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert 'pip install "spotapi[demo]"' in captured.err
    launch.assert_not_called()


def test_cli_studio_explains_the_optional_install(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=None))
    launch = Mock()
    monkeypatch.setattr("spotapi.cli.importlib.import_module", launch)
    assert main(["studio"]) == 1
    assert 'pip install "spotapi[studio]"' in capsys.readouterr().err
    launch.assert_not_called()


def test_cli_studio_lets_the_native_app_own_its_event_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    desktop = Mock()
    monkeypatch.setattr("spotapi.cli.importlib.import_module", Mock(return_value=desktop))
    runner = Mock(side_effect=AssertionError("Native Studio must own its event loop"))
    monkeypatch.setattr("spotapi.cli.asyncio.run", runner)
    assert main(["studio"]) == 0
    desktop.main.assert_called_once_with()


def test_cli_discover_launches_outside_the_async_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    launch = Mock()
    monkeypatch.setattr("spotapi.cli.importlib.import_module", Mock(return_value=launch))
    runner = Mock(side_effect=AssertionError("Textual must own its event loop"))
    monkeypatch.setattr("spotapi.cli.asyncio.run", runner)
    assert main(["discover", "Daft", "Punk"]) == 0
    launch.main.assert_called_once_with("Daft Punk")
    runner.assert_not_called()


def test_cli_empty_search_keeps_stdout_clean(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Public, "search", AsyncMock(return_value=SearchResults("abc", ("track",))))

    assert main(["search", "abc"]) == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "No tracks found" in captured.err


def test_cli_reports_spotify_error_without_traceback(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(Public, "search", AsyncMock(side_effect=SpotAPIError("Request failed")))

    assert main(["search", "abc"]) == 1
    assert capsys.readouterr().err == "spotapi: Request failed\n"


def test_cli_requires_a_session_for_playlist_changes(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("SPOTIFY_COOKIE", raising=False)

    assert main(["playlist", "remove", "playlist", "occurrence"]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "Set SPOTIFY_COOKIE" in captured.err


def test_cli_passes_the_exact_occurrence_to_playlist_move(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    @asynccontextmanager
    async def session(cookie: str) -> AsyncGenerator[object, None]:
        assert cookie == "test-cookie"
        yield SimpleNamespace(session=Mock(spec=AuthSession, client=Mock(spec=AsyncClient)))

    move = AsyncMock()
    monkeypatch.setenv("SPOTIFY_COOKIE", "test-cookie")
    monkeypatch.setattr(Private, "from_cookies", session)
    monkeypatch.setattr(Playlist, "move_occurrences", move)

    assert main(["playlist", "move", "playlist", "second", "--before", "first"]) == 0
    move.assert_awaited_once_with("second", before="first", after=None)
    assert not capsys.readouterr().out


@pytest.mark.parametrize(
    ("argv", "message"),
    [
        (["player", "seek", "-1"], "non-negative"),
        (["player", "volume", "-1"], "from 0 to 100"),
        (["player", "volume", "101"], "from 0 to 100"),
    ],
)
def test_cli_rejects_invalid_player_values_before_connecting(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    argv: list[str],
    message: str,
) -> None:
    connect = Mock(side_effect=AssertionError("CLI must reject input before connecting"))
    monkeypatch.setattr(Private, "from_cookies", connect)

    with pytest.raises(SystemExit) as exit_info:
        main(argv)

    assert exit_info.value.code == 2
    assert message in capsys.readouterr().err
    connect.assert_not_called()


@pytest.mark.parametrize(
    ("argv", "method", "value"),
    [
        (["player", "seek", "0"], "seek", 0),
        (["player", "volume", "0"], "volume", 0),
        (["player", "volume", "100"], "volume", 100),
    ],
)
def test_cli_accepts_player_boundary_values(
    monkeypatch: pytest.MonkeyPatch,
    argv: list[str],
    method: str,
    value: int,
) -> None:
    controller = Mock()
    controller.seek = AsyncMock()
    controller.volume = AsyncMock()

    @asynccontextmanager
    async def session(_cookie: str) -> AsyncGenerator[SimpleNamespace, None]:
        yield SimpleNamespace(session=Mock())

    @asynccontextmanager
    async def connect() -> AsyncGenerator[Mock, None]:
        yield controller

    fake_player = Mock()
    fake_player.connect = connect
    monkeypatch.setenv("SPOTIFY_COOKIE", "test-cookie")
    monkeypatch.setattr(Private, "from_cookies", session)
    monkeypatch.setattr("spotapi.cli.Player", Mock(return_value=fake_player))

    assert main(argv) == 0
    getattr(controller, method).assert_awaited_once_with(value)
