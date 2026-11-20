"""Import boundaries must survive pagination and partial source failures."""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from examples.taste_lab import spotify
from examples.taste_lab.models import Song
from examples.taste_lab.store import Store
from spotapi import Catalogue
from spotapi.session import AuthSession
from spotapi.types import BaseClientError


async def test_nested_library_folders_are_paginated_and_cycles_are_ignored(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str | None] = []

    class Library:
        def __init__(self, session: AuthSession) -> None:
            pass

        async def pages(self, *, folder: str | None) -> AsyncIterator[SimpleNamespace]:
            visited.append(folder)
            if folder is None:
                yield SimpleNamespace(items=[SimpleNamespace(kind="folder", uri="folder")])
                yield SimpleNamespace(items=[SimpleNamespace(kind="album", uri="album")])
            else:
                yield SimpleNamespace(
                    items=[
                        SimpleNamespace(kind="folder", uri="folder"),
                        SimpleNamespace(kind="playlist", uri="playlist"),
                    ]
                )

    monkeypatch.setattr(spotify, "Library", Library)
    result = await spotify._library_resources(cast(AuthSession, object()))

    assert result == {"album": "album", "playlist": "playlist"}
    assert visited == [None, "folder"]


async def test_failed_source_retains_previous_import_and_does_not_delete_stale_sources(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = Store(tmp_path / "profile.sqlite3")
    song = Song("spotify:track:remember", "Remember", (), ())
    store.replace_source("playlist:playlist", [song], 0.75)
    store.replace_source("playlist:old", [song], 0.75)

    class LikedTracks:
        def __init__(self, session: AuthSession) -> None:
            pass

        async def pages(self) -> AsyncIterator[list[object]]:
            yield []

    async def resources(session: AuthSession) -> dict[str, str]:
        return {"playlist": "playlist"}

    async def failed(catalogue: Catalogue, uri: str, kind: str) -> list[Song]:
        raise BaseClientError("broken second page")

    monkeypatch.setattr(spotify, "LikedTracks", LikedTracks)
    monkeypatch.setattr(spotify, "_library_resources", resources)
    monkeypatch.setattr(spotify, "_read_resource", failed)
    result = await spotify.sync_library(
        cast(Catalogue, object()),
        cast(AuthSession, object()),
        store,
        lambda _: None,
    )

    assert result.failures
    assert {seed.source for seed in store.snapshot().seeds} == {
        "playlist:playlist",
        "playlist:old",
    }
