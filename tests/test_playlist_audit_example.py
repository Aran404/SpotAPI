"""Offline tests for the public-playlist CSV audit example."""

from __future__ import annotations

import csv
from collections.abc import AsyncGenerator
from pathlib import Path

import pytest

from examples.playlist_audit import export_playlist
from spotapi.models.catalogue.entities import Episode
from spotapi.models.catalogue.playlist_details import PlaylistEntry
from spotapi.models.catalogue.playlist_track import PlaylistTrack
from spotapi.models.catalogue.track import ArtistItem, ArtistProfile, Artists, Duration


async def sample_entries() -> AsyncGenerator[PlaylistEntry, None]:
    artists = Artists(items=[ArtistItem(uri="spotify:artist:a", profile=ArtistProfile("A, B"))])
    song = PlaylistTrack(
        name="Song", uri="spotify:track:s", artists=artists, track_duration=Duration(42_000)
    )
    yield PlaylistEntry(item=song, uid="first", added_at="2026-01-01")
    yield PlaylistEntry(item=song, uid="second")
    yield PlaylistEntry(item=Episode(name="Talk", uri="spotify:episode:e"), uid="third")
    yield PlaylistEntry(item=None, uid="unavailable")


@pytest.mark.asyncio
async def test_exports_all_occurrences_and_counts(tmp_path: Path) -> None:
    output = tmp_path / "report.csv"
    summary = await export_playlist(sample_entries(), output)
    with output.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))

    assert (summary.scanned, summary.tracks, summary.unique_tracks) == (4, 2, 1)
    assert (summary.repeated_tracks, summary.episodes, summary.unavailable) == (1, 1, 1)
    assert [row["kind"] for row in rows] == ["track", "track", "episode", "unavailable"]
    assert [row["duplicate"] for row in rows] == ["0", "1", "0", "0"]
    assert rows[0]["artists"] == "A, B"
    assert rows[0]["duration_ms"] == "42000"
    assert [row["occurrence_id"] for row in rows] == ["first", "second", "third", "unavailable"]
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.asyncio
async def test_early_limit_closes_generator_without_overfetch(tmp_path: Path) -> None:
    pulled: list[int] = []
    closed: list[bool] = []

    async def entries() -> AsyncGenerator[PlaylistEntry, None]:
        try:
            for number in range(10):
                pulled.append(number)
                yield PlaylistEntry(item=None)
        finally:
            closed.append(True)

    output = tmp_path / "limited.csv"
    summary = await export_playlist(entries(), output, max_items=2)
    assert summary.scanned == 2
    assert pulled == [0, 1]
    assert closed == [True]


@pytest.mark.asyncio
async def test_failed_read_does_not_leave_partial_csv(tmp_path: Path) -> None:
    async def failing() -> AsyncGenerator[PlaylistEntry, None]:
        yield PlaylistEntry(item=None)
        raise RuntimeError("upstream read failed")

    with pytest.raises(RuntimeError, match="upstream"):
        await export_playlist(failing(), tmp_path / "report.csv")
    assert list(tmp_path.iterdir()) == []


@pytest.mark.asyncio
async def test_refuses_existing_output_and_invalid_limits(tmp_path: Path) -> None:
    output = tmp_path / "existing.csv"
    output.write_text("previous version", encoding="utf-8")
    with pytest.raises(FileExistsError):
        await export_playlist(sample_entries(), output)
    assert output.read_text(encoding="utf-8") == "previous version"
    for count in (0, 10_001):
        with pytest.raises(ValueError, match="max_items"):
            await export_playlist(sample_entries(), tmp_path / "new.csv", max_items=count)
