"""Exercise command output and failure status without network access."""

import json
from unittest.mock import AsyncMock

import pytest

from spotapi import Public, SearchResults, SpotAPIError
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
