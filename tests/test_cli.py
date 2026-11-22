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
from spotapi.cli import _parser, main
from spotapi.types import BaseClientError
from spotapi.login import SavedSession


@pytest.mark.parametrize(
    ("action", "value"), [("seek", "-1"), ("volume", "-1"), ("volume", "101")]
)
def test_cli_rejects_invalid_player_values_before_running(
    action: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    runner = Mock()
    monkeypatch.setattr("spotapi.cli.asyncio.run", runner)

    with pytest.raises(SystemExit) as exit_info:
        main(["player", action, value])

    assert exit_info.value.code == 2
    runner.assert_not_called()


@pytest.mark.parametrize(
    ("action", "value", "field"),
    [("seek", "0", "milliseconds"), ("volume", "0", "percent"), ("volume", "100", "percent")],
)
def test_cli_accepts_player_range_boundaries(action: str, value: str, field: str) -> None:
    args = _parser().parse_args(["player", action, value])

    assert getattr(args, field) == int(value)


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


def test_cli_discovery_dispatches_to_its_declared_lookup(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lookup = AsyncMock(return_value={"title": "Editorial chart"})
    monkeypatch.setattr(Public, "get_chart", lookup)

    assert main(["chart", "top"]) == 0
    lookup.assert_awaited_once_with("top")
    assert json.loads(capsys.readouterr().out) == {"title": "Editorial chart"}


def test_cli_search_accepts_the_python_search_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    search = AsyncMock(return_value=SearchResults("abc", ("track",)))
    monkeypatch.setattr(Public, "search", search)

    assert main(["search", "abc", "--limit", "100"]) == 0
    search.assert_awaited_once_with("abc", types="track", limit=100, language=None)


def test_cli_json_search_omits_progress_on_a_terminal(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("spotapi.cli.sys.stderr.isatty", lambda: True)
    search = AsyncMock(return_value=SearchResults("Daft Punk", ("artist",)))
    monkeypatch.setattr(Public, "search", search)

    assert main(["search", "Daft Punk", "--type", "artist", "--json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == []
    assert captured.err == ""


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
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    monkeypatch.setattr(
        SavedSession, "open", AsyncMock(side_effect=BaseClientError("No saved session"))
    )

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


@pytest.mark.parametrize("language", ["fr-CA", "de-DE"])
def test_cli_forwards_search_language(language: str, monkeypatch: pytest.MonkeyPatch) -> None:
    search = AsyncMock(return_value=SearchResults("test", ("artist",)))
    monkeypatch.setattr(Public, "search", search)

    assert main(["search", "test", "--type", "artist", "--language", language, "--json"]) == 0
    search.assert_awaited_once_with("test", types="artist", limit=10, language=language)


def test_cli_reuses_saved_connect_profile_without_reauthenticating(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """A saved Connect login works for ordinary CLI commands without an env cookie."""
    monkeypatch.delenv("SPOTIFY_COOKIE", raising=False)
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    client = AsyncMock()
    client.__aenter__.return_value = client
    open_saved = AsyncMock(return_value=client)
    monkeypatch.setattr(SavedSession, "open", open_saved)
    liked = SimpleNamespace(get=AsyncMock(return_value=()))
    account = SimpleNamespace(liked_tracks=liked)
    construct_account = Mock(return_value=account)
    monkeypatch.setattr("spotapi.cli.Private", construct_account)

    assert main(["library", "list"]) == 0

    open_saved.assert_awaited_once_with()
    construct_account.assert_called_once_with(client)
    liked.get.assert_awaited_once_with(limit=20)
    client.__aexit__.assert_awaited_once()
    assert not capsys.readouterr().err


def test_cli_explicit_profile_overrides_environment_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SPOTIFY_COOKIE", "different-account-cookie")
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    client = AsyncMock()
    client.__aenter__.return_value = client
    open_saved = AsyncMock(return_value=client)
    monkeypatch.setattr(SavedSession, "open", open_saved)
    liked = SimpleNamespace(get=AsyncMock(return_value=()))
    monkeypatch.setattr(
        "spotapi.cli.Private", Mock(return_value=SimpleNamespace(liked_tracks=liked))
    )

    assert main(["library", "list", "--profile", "personal"]) == 0

    open_saved.assert_awaited_once_with()
    liked.get.assert_awaited_once_with(limit=20)


def test_cli_rejects_invalid_profile_before_keyring_access(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    open_saved = AsyncMock()
    monkeypatch.setattr(SavedSession, "open", open_saved)

    assert main(["player", "status", "--profile", "../bad"]) == 1
    assert "Profile must be" in capsys.readouterr().err
    open_saved.assert_not_awaited()


def test_cli_says_how_to_recover_when_named_profile_is_absent(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    from spotapi.types import BaseClientError

    monkeypatch.delenv("SPOTIFY_COOKIE", raising=False)
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    monkeypatch.setattr(
        SavedSession, "open", AsyncMock(side_effect=BaseClientError("Missing saved profile"))
    )

    assert main(["library", "list", "--profile", "missing"]) == 1
    error = capsys.readouterr().err
    assert "spotapi connect" in error
    assert "Set SPOTIFY_COOKIE" in error
    assert "Missing saved profile" not in error


def test_cli_reports_missing_secure_keyring_backend(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A headless Linux installation needs an actionable session fallback."""
    class NoKeyringError(Exception):
        pass

    monkeypatch.delenv("SPOTIFY_COOKIE", raising=False)
    monkeypatch.setattr("spotapi.cli.importlib.util.find_spec", Mock(return_value=object()))
    old_import = __import__("importlib").import_module

    def import_module(name: str, package: str | None = None) -> object:
        if name == "keyring.errors":
            return SimpleNamespace(NoKeyringError=NoKeyringError)
        return old_import(name, package)

    monkeypatch.setattr("spotapi.cli.importlib.import_module", import_module)
    monkeypatch.setattr(
        SavedSession, "open", AsyncMock(side_effect=NoKeyringError("No recommended backend"))
    )

    assert main(["playlist", "remove", "playlist", "occurrence"]) == 1
    captured = capsys.readouterr()
    assert not captured.out
    assert "Set SPOTIFY_COOKIE" in captured.err
    assert "keyring backend" in captured.err
    assert "No recommended backend" not in captured.err
