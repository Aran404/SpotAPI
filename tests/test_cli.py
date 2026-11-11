"""Exercise command output and failure status without network access."""

import json
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from spotapi import Playlist, Private, Public, SearchResults, SpotAPIError
from spotapi.cli import main


def test_cli_get_outputs_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    resource = Public.parse_url("spotify:track:abc")
    monkeypatch.setattr(Public, "get", AsyncMock(return_value=resource))

    assert main(["get", resource.uri]) == 0
    assert json.loads(capsys.readouterr().out)["uri"] == resource.uri


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
        yield SimpleNamespace(session=object())

    move = AsyncMock()
    monkeypatch.setenv("SPOTIFY_COOKIE", "test-cookie")
    monkeypatch.setattr(Private, "from_cookies", session)
    monkeypatch.setattr(Playlist, "move_occurrences", move)

    assert main(["playlist", "move", "playlist", "second", "--before", "first"]) == 0
    move.assert_awaited_once_with("second", before="first", after=None)
    assert not capsys.readouterr().out
