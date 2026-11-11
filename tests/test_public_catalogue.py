"""Public contracts for real-key search, occurrence identity and music metadata."""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import Any, cast

import pytest

from spotapi import Public
from spotapi import catalogue as catalogue
from spotapi.datastruct import ObjectDict
from spotapi.models import (
    Audiobook,
    Author,
    Episode,
    Genre,
    PlaylistTrack,
    PublicProfile,
    User,
)
from spotapi.queries import Queries


def test_all_search_categories_have_typed_payloads(monkeypatch: pytest.MonkeyPatch) -> None:
    sections = {
        "audiobooks": {"name": "Book", "uri": "spotify:show:book"},
        "episodes": {"name": "Episode", "uri": "spotify:episode:episode"},
        "users": {"displayName": "Person", "uri": "spotify:user:person"},
        "authors": {"name": "Author", "uri": "spotify:author:author"},
        "genres": {"name": "Jazz", "uri": "spotify:genre:jazz"},
    }
    calls: list[str] = []

    async def query(self: Queries, operation: str, variables: dict[str, Any]):
        calls.append(operation)

        return ObjectDict(
            {"searchV2": {key: {"items": [{"data": value}]} for key, value in sections.items()}}
        )

    monkeypatch.setattr(Queries, "query", query)

    result = asyncio.run(
        Public.search("anything", types=("audiobook", "episode", "user", "author", "genre"))
    )

    for values, model in [
        (result.audiobooks, Audiobook),
        (result.episodes, Episode),
        (result.users, User),
        (result.authors, Author),
        (result.genres, Genre),
    ]:
        assert len(values) == 1 and isinstance(values[0], model)

    assert calls == ["searchDesktop"]


def test_playlist_preserves_duplicates_episodes_and_unavailable_occurrences() -> None:
    values = [
        {
            "uid": "first",
            "itemV2": {"data": {"name": "Song", "uri": "spotify:track:track"}},
        },
        {
            "uid": "second",
            "itemV2": {"data": {"name": "Song", "uri": "spotify:track:track"}},
        },
        {"uid": "removed", "itemV2": {"data": None}},
        {
            "uid": "episode",
            "itemV2": {"data": {"name": "Episode", "uri": "spotify:episode:episode"}},
        },
    ]
    entries = [catalogue._playlist_entry(ObjectDict(value)) for value in values]

    assert len(entries) == 4
    assert entries[0].uri == entries[1].uri
    assert entries[0].uid != entries[1].uid
    assert entries[2].item is None
    assert isinstance(entries[3].item, Episode)


def test_playlist_audio_metadata_is_optional_and_typed() -> None:
    entry = catalogue._playlist_entry(
        ObjectDict(
            {
                "itemV2": {
                    "data": {
                        "name": "Song",
                        "uri": "spotify:track:track",
                        "playlistAudioAttributes": {
                            "bpm": 128,
                            "key": {
                                "key": "E",
                                "mode": "MODE_MAJOR",
                                "camelotKey": {"value": "12B"},
                            },
                        },
                    }
                }
            }
        )
    )

    assert isinstance(entry.item, PlaylistTrack)
    assert entry.item.bpm == 128.0
    assert entry.item.musical_key is not None
    assert entry.item.musical_key.camelot_key is not None
    assert entry.item.musical_key.camelot_key.value == "12B"
    assert asdict(entry.item)["playlist_audio_attributes"]["bpm"] == 128.0
    assert PlaylistTrack(name="Minimal", uri="spotify:track:minimal").bpm is None


@pytest.mark.parametrize("value", [0, 101, True, -1])
def test_new_page_helpers_reject_invalid_limits(value: int) -> None:
    async def run() -> None:
        for stream in (
            Public.get_playlist_items("id", limit=cast(Any, value)),
            Public.get_album_tracks("id", limit=cast(Any, value)),
            Public.get_artist_releases("id", limit=cast(Any, value)),
        ):
            with pytest.raises(ValueError, match="between 1 and 100"):
                await anext(stream)

    asyncio.run(run())


def test_profile_request_encodes_username_and_binds_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def get_json(self: Queries, url: str, *, query: dict[str, str]) -> ObjectDict:
        calls.append((url, query))

        return ObjectDict(
            {
                "name": "A curator",
                "uri": "spotify:user:a%20name",
                "followers_count": 5,
                "public_playlists": [],
            }
        )

    monkeypatch.setattr(Queries, "get_json", get_json)

    profile = asyncio.run(Public.get_profile("a%20name", limit=3))

    assert isinstance(profile, PublicProfile)
    assert calls[0][0].endswith("a%2520name")
    assert calls[0][1]["playlist_limit"] == "3"


def test_credits_use_the_actual_track_uri_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, dict[str, Any]]] = []

    async def query(self: Queries, operation: str, variables: dict[str, Any]):
        calls.append((operation, variables))

        return ObjectDict(
            {
                "trackUnion": {
                    "creditsTrait": {
                        "contributors": {
                            "items": [{"name": "Producer", "role": "Producer", "uri": None}]
                        }
                    }
                }
            }
        )

    monkeypatch.setattr(Queries, "query", query)

    credits = asyncio.run(Public.get_track_credits("track-id"))

    assert credits.contributors[0].name == "Producer"
    assert calls == [("queryTrackCreditsGroupedModal", {"trackUri": "spotify:track:track-id"})]


def test_show_links_distinguish_audiobooks_from_podcasts(monkeypatch: pytest.MonkeyPatch) -> None:
    async def query(self: Queries, operation: str, variables: dict[str, Any]):
        return ObjectDict(
            {
                "podcastUnionV2": {
                    "__typename": "Audiobook",
                    "name": "Dune",
                    "uri": variables["uri"],
                    "authorsV2": [{"name": "Frank Herbert", "uri": "spotify:author:author"}],
                }
            }
        )

    monkeypatch.setattr(Queries, "query", query)

    result = asyncio.run(Public.get("spotify:show:book"))

    assert isinstance(result, Audiobook)
    assert result.authors_v2[0].name == "Frank Herbert"

    with pytest.raises(ValueError, match="audiobook"):
        asyncio.run(Public.get_podcast("spotify:show:book"))

    assert isinstance(asyncio.run(Public.get("book", kind="audiobook")), Audiobook)
