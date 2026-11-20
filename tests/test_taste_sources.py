"""Automatic audio matching must reject plausible but different recordings."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from examples.taste_lab.models import Candidate, Seed, Snapshot, Song
from examples.taste_lab.store import Store
from examples.taste_lab.youtube import match, selection

SONG = Song("spotify:track:example", "Example", ("spotify:artist:a",), ("Artist",), 180_000)


def row(**changes: object) -> dict[str, object]:
    result: dict[str, object] = {
        "id": "abcdefghijk",
        "title": "Example",
        "channel": "Artist - Topic",
        "duration": 180,
    }
    result.update(changes)
    return result


def test_topic_recording_requires_matching_title_artist_and_duration() -> None:
    assert match(SONG, [row()]) is not None
    assert match(SONG, [row(title="Example (Live)")]) is None
    assert match(SONG, [row(channel="Different Artist - Topic")]) is None
    assert match(SONG, [row(duration=200)]) is None
    assert match(SONG, [row(duration=float("nan"))]) is None
    assert match(SONG, [row(id="../../file")]) is None


def test_official_artist_channel_requires_verification() -> None:
    entry = row(title="Artist - Example (Official Audio)", channel="Artist")
    assert match(SONG, [entry]) is None
    assert match(SONG, [entry], verified=False) is not None
    entry["channel_is_verified"] = True
    assert match(SONG, [entry]) is not None


def test_conflicting_matches_are_not_resolved_by_popularity() -> None:
    assert match(SONG, [row(), row(id="lmnopqrstuv")]) is None
    assert match(SONG, [row(), row()]) is not None


def test_selection_alternates_seeds_and_candidates_and_advances_past_cache() -> None:
    first, second = SONG, replace(SONG, uri="spotify:track:other", artists=("spotify:artist:b",))
    third = replace(SONG, uri="spotify:track:third", artists=("spotify:artist:c",))
    snapshot = Snapshot(
        (Seed("liked", first, 2),), (Candidate(second, ()), Candidate(third, ())), (), {}
    )

    assert selection(snapshot, 2) == (first, second)
    assert selection(snapshot, 2, exclude={first.uri}) == (second, third)


def test_failed_sources_are_deferred_for_an_hour_without_hiding_audio_forever(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "profile.sqlite3")
    store.audio_attempt(SONG.uri, "failed", 1000)
    assert store.deferred_audio(1001) == {SONG.uri}
    assert store.deferred_audio(4601) == set()
    store.audio_attempt(SONG.uri, "unmatched", 5000)
    assert store.deferred_audio(5001) == {SONG.uri}
    assert store.deferred_audio(91_401) == set()
