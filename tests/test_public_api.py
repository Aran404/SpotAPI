"""Offline tests for Spotify URL resolution and high-level public methods."""

from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any, cast
from unittest.mock import Mock

import pytest

from spotapi import catalogue as public_module
from spotapi.catalogue import Catalogue
from spotapi.datastruct import ObjectDict
from spotapi.operations import InclusionParameters, Operations
from spotapi.public import Public, SearchResults, SpotifyResource
from spotapi.queries import Queries

TRACK_ID = "39MK3d3fonIP8Mz9oHCTBB"
ARTIST_ID = "0OdUWJ0sBjDrqHygGUXeCF"
PLAYLIST_ID = "37i9dQZF1DXcBWIGoYBM5M"


def test_parse_track_share_url_ignores_si_parameter() -> None:
    """Spotify's ``si`` tracking parameter must not become part of the ID."""
    resource = Public.parse_url(f"https://open.spotify.com/track/{TRACK_ID}?si=765229d9bcf4459f")

    assert resource == SpotifyResource(
        kind="track",
        id=TRACK_ID,
        uri=f"spotify:track:{TRACK_ID}",
        url=f"https://open.spotify.com/track/{TRACK_ID}",
    )


def test_parse_url_ignores_all_query_and_fragment_parameters() -> None:
    resource = Public.parse_url(f"https://open.spotify.com/track/{TRACK_ID}?si=abc&nd=1#somewhere")

    assert resource.id == TRACK_ID
    assert resource.uri == f"spotify:track:{TRACK_ID}"


@pytest.mark.parametrize(
    ("url", "expected_kind", "expected_id"),
    [
        (
            f"https://open.spotify.com/intl-en/track/{TRACK_ID}?si=abc",
            "track",
            TRACK_ID,
        ),
        (
            f"https://open.spotify.com/embed/track/{TRACK_ID}?utm_source=generator",
            "track",
            TRACK_ID,
        ),
        (
            "https://open.spotify.com/embed-podcast/episode/5CZlLoGOibAGX9oLh26YEk?si=abc",
            "episode",
            "5CZlLoGOibAGX9oLh26YEk",
        ),
        (
            f"https://open.spotify.com/user/example/playlist/{PLAYLIST_ID}?si=abc",
            "playlist",
            PLAYLIST_ID,
        ),
    ],
)
def test_parse_supported_url_variants(
    url: str,
    expected_kind: str,
    expected_id: str,
) -> None:
    resource = Public.parse_url(url)

    assert resource.kind == expected_kind
    assert resource.id == expected_id


@pytest.mark.parametrize(
    ("uri", "expected_kind", "expected_id"),
    [
        (f"spotify:track:{TRACK_ID}", "track", TRACK_ID),
        ("spotify:podcast:abc123", "show", "abc123"),
        ("spotify:show:abc123", "show", "abc123"),
        (
            f"spotify:user:listener:playlist:{PLAYLIST_ID}",
            "playlist",
            PLAYLIST_ID,
        ),
    ],
)
def test_parse_spotify_uris(
    uri: str,
    expected_kind: str,
    expected_id: str,
) -> None:
    resource = Public.parse_url(uri)

    assert resource.kind == expected_kind
    assert resource.id == expected_id


def test_parse_bare_id_requires_and_uses_kind() -> None:
    resource = Public.parse_url(TRACK_ID, kind="track")

    assert resource.kind == "track"
    assert resource.uri == f"spotify:track:{TRACK_ID}"


def test_parse_bare_id_rejects_ambiguous_input() -> None:
    with pytest.raises(ValueError, match="bare Spotify ID is ambiguous"):
        Public.parse_url(TRACK_ID)


def test_parse_rejects_conflicting_kind() -> None:
    with pytest.raises(ValueError, match="Resource is a track"):
        Public.parse_url(f"https://open.spotify.com/track/{TRACK_ID}", kind="album")


@pytest.mark.parametrize(
    "value",
    [
        "",
        "   ",
        "https://example.com/track/abc",
        "https://open.spotify.com/unknown/abc",
        "https://open.spotify.com/track",
        "spotify:track:",
        "spotify:local:artist:album:title:123",
        "bad id",
        "https://spotify.link/short-code",
    ],
)
def test_parse_rejects_invalid_inputs(value: str) -> None:
    with pytest.raises(ValueError):
        Public.parse_url(value)


def test_parse_resource_kind_is_case_insensitive() -> None:
    resource = Public.parse_url(f"https://OPEN.SPOTIFY.COM/track/{TRACK_ID}")

    assert resource.id == TRACK_ID


def test_parse_url_returns_immutable_descriptor() -> None:
    resource = Public.parse_url(f"https://open.spotify.com/track/{TRACK_ID}")

    with pytest.raises(AttributeError):
        resource.__setattr__("id", "changed")


def test_search_results_support_singular_plural_aliases() -> None:
    results = SearchResults(query="test", requested_types=("podcast",))

    assert results["podcast"] == results.podcasts
    assert results["shows"] == results.podcasts
    assert results["tracks"] == results.tracks
    assert not results
    assert len(results) == 0


def test_search_results_report_total_count() -> None:
    results = SearchResults(
        query="test",
        requested_types=("track", "album"),
        tracks=(cast(Any, object()), cast(Any, object())),
        albums=(cast(Any, object()),),
    )

    assert bool(results)
    assert len(results) == 3


def test_search_results_reject_unknown_key() -> None:
    results = SearchResults(query="test", requested_types=("track",))

    with pytest.raises(ValueError, match="Unsupported Spotify search type"):
        results["invalid"]


def test_get_dispatches_track_and_ignores_si(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    sentinel = object()

    async def fake_get_track(uri: str) -> Any:
        called.append(uri)

        return sentinel

    monkeypatch.setattr(Catalogue, "get_track", staticmethod(fake_get_track))

    async def scenario() -> None:
        result = await Public.get(f"https://open.spotify.com/track/{TRACK_ID}?si=share-token")

        assert result is sentinel

    asyncio.run(scenario())

    assert called == [f"spotify:track:{TRACK_ID}"]


def test_get_dispatches_playlist_to_metadata_operation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Operations]] = []
    sentinel = ObjectDict()

    async def fake_get_resource(
        uri: str,
        operation: Operations,
        typ: type[Any] | None = None,
    ) -> ObjectDict:
        calls.append((uri, operation))

        return sentinel

    monkeypatch.setattr(Catalogue, "get_resource", staticmethod(fake_get_resource))

    async def scenario() -> None:
        result = await Public.get(f"https://open.spotify.com/playlist/{PLAYLIST_ID}?si=share")

        assert result is sentinel

    asyncio.run(scenario())

    assert calls == [(f"spotify:playlist:{PLAYLIST_ID}", Operations.FETCH_PLAYLIST_METADATA)]


def test_get_requires_kind_for_bare_id() -> None:
    async def scenario() -> None:
        with pytest.raises(ValueError, match="bare Spotify ID is ambiguous"):
            await Public.get(TRACK_ID)

    asyncio.run(scenario())


class _FakeQueries:
    """Minimal fake transport used to verify one-request grouped searches."""

    calls: list[tuple[str, Mapping[str, Any]]]

    def __init__(self) -> None:
        self.calls = []

    async def query(
        self,
        operation: str,
        variables: Mapping[str, Any],
    ) -> ObjectDict:
        self.calls.append((operation, variables))

        return ObjectDict(
            {
                "searchV2": ObjectDict(
                    {
                        "tracksV2": ObjectDict({"items": []}),
                        "artists": ObjectDict({"items": []}),
                        "albums": ObjectDict({"items": []}),
                        "playlists": ObjectDict({"items": []}),
                        "podcasts": ObjectDict({"items": []}),
                    }
                )
            }
        )

    parse_items = staticmethod(Queries.parse_items)
    parse_raw_items = staticmethod(Queries.parse_raw_items)


def test_search_uses_one_consolidated_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeQueries()

    monkeypatch.setattr(public_module, "Queries", Mock(return_value=fake))

    async def scenario() -> None:
        results = await Public.search("  Daft Punk  ", types=("artists", "albums", "tracks"))

        assert results.query == "Daft Punk"
        assert results.requested_types == ("artist", "album", "track")
        assert results.artists == ()
        assert results.albums == ()
        assert results.tracks == ()

    asyncio.run(scenario())

    assert len(fake.calls) == 1
    operation, variables = fake.calls[0]

    assert operation == Operations.SEARCH_DESKTOP.value
    assert variables["searchTerm"] == "Daft Punk"
    assert variables["limit"] == 20


def test_search_accepts_single_string_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeQueries()

    monkeypatch.setattr(public_module, "Queries", Mock(return_value=fake))

    async def scenario() -> None:
        results = await Public.search("Radiohead", types="track")

        assert results.requested_types == ("track",)

    asyncio.run(scenario())

    assert len(fake.calls) == 1


def test_search_honours_inclusion_parameters_without_mutating_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeQueries()

    monkeypatch.setattr(public_module, "Queries", Mock(return_value=fake))

    parameters = InclusionParameters(limit=40, includePreReleases=True)

    async def scenario() -> None:
        await Public.search(
            "fantasy",
            types=("audiobook", "author", "episode"),
            parameters=parameters,
        )

    asyncio.run(scenario())

    assert parameters.limit == 40
    assert parameters.includeAudiobooks is False
    assert parameters.includeAuthors is False
    assert parameters.includeEpisodeContentRatingsV2 is False
    assert len(fake.calls) == 1
    operation, variables = fake.calls[0]

    assert operation == Operations.SEARCH_DESKTOP.value
    assert variables["includeAudiobooks"] is True
    assert variables["includeAuthors"] is True
    assert variables["includeEpisodeContentRatingsV2"] is True


def test_search_rejects_empty_query_empty_types_and_invalid_limit() -> None:
    async def scenario() -> None:
        with pytest.raises(ValueError, match="Search query must not be empty"):
            await Public.search("   ")

        with pytest.raises(ValueError, match="At least one search type"):
            await Public.search("test", types=())

        with pytest.raises(ValueError, match="Unsupported Spotify search type"):
            await Public.search("test", types=cast(Any, ("not-a-kind",)))

        with pytest.raises(ValueError, match="between 1 and 100"):
            await Public.search("test", limit=0)

        with pytest.raises(ValueError, match="between 1 and 100"):
            await Public.search("test", limit=101)

        with pytest.raises(ValueError, match="between 1 and 100"):
            await Public.search("test", limit=cast(Any, True))

    asyncio.run(scenario())


def test_search_extended_categories_use_one_desktop_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeQueries()

    monkeypatch.setattr(public_module, "Queries", Mock(return_value=fake))

    async def scenario() -> None:
        results = await Public.search(
            "podcast name", types=("audiobook", "episode", "author", "genre", "user")
        )

        assert results.requested_types == (
            "audiobook",
            "episode",
            "author",
            "genre",
            "user",
        )
        assert results.audiobooks == ()
        assert results.episodes == ()
        assert results.authors == ()
        assert results.genres == ()
        assert results.users == ()

    asyncio.run(scenario())

    assert len(fake.calls) == 1
    assert fake.calls[0][0] == Operations.SEARCH_DESKTOP.value


def test_get_resource_normalizes_si_url_before_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Operations, type[Any] | None]] = []
    payload = ObjectDict({"ok": True})

    class _ResourceWrapper:
        async def resource(
            self,
            uri: str,
            operation: Operations,
            typ: type[Any] | None = None,
        ) -> Any:
            calls.append((uri, operation, typ))

            return payload

    monkeypatch.setattr(public_module, "Queries", Mock(return_value=_ResourceWrapper()))

    async def scenario() -> None:
        result = await Public.get_resource(
            f"https://open.spotify.com/track/{TRACK_ID}?si=share",
            Operations.GET_TRACK,
        )

        assert result is payload

    asyncio.run(scenario())

    assert calls == [(f"spotify:track:{TRACK_ID}", Operations.GET_TRACK, None)]


def test_get_track_accepts_a_bare_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Operations, type[Any] | None]] = []
    track = type(
        "TrackStub",
        (),
        {
            "id": TRACK_ID,
            "name": "Example",
            "duration": type("DurationStub", (), {"total_milliseconds": 1})(),
        },
    )()

    async def fake_get_resource(
        uri: str,
        operation: Operations,
        typ: type[Any] | None = None,
    ) -> Any:
        calls.append((uri, operation, typ))

        return track

    monkeypatch.setattr(Catalogue, "get_resource", staticmethod(fake_get_resource))

    async def scenario() -> None:
        result = await Public.get_track(TRACK_ID)

        assert result is track

    asyncio.run(scenario())

    assert calls == [
        (f"spotify:track:{TRACK_ID}", Operations.GET_TRACK, public_module.TrackDetails)
    ]


def test_get_album_accepts_a_bare_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, Operations, type[Any] | None]] = []
    album = type("AlbumStub", (), {"id": "album-id", "name": "Album"})()

    async def fake_get_resource(
        uri: str,
        operation: Operations,
        typ: type[Any] | None = None,
    ) -> Any:
        calls.append((uri, operation, typ))

        return album

    monkeypatch.setattr(Catalogue, "get_resource", staticmethod(fake_get_resource))

    async def scenario() -> None:
        assert await Public.get_album("album-id") is album

    asyncio.run(scenario())

    assert calls == [("spotify:album:album-id", Operations.GET_ALBUM, public_module.AlbumDetails)]


@pytest.mark.parametrize(
    ("resource_kind", "operation"),
    [
        ("chapter", Operations.GET_EPISODE_OR_CHAPTER),
    ],
)
def test_get_dispatches_unmodeled_resource_types(
    monkeypatch: pytest.MonkeyPatch,
    resource_kind: str,
    operation: Operations,
) -> None:
    calls: list[tuple[str, Operations]] = []
    sentinel = ObjectDict({"resource": "ok"})

    async def fake_get_resource(
        uri: str, selected_operation: Operations, typ: type[Any] | None = None
    ) -> ObjectDict:
        calls.append((uri, selected_operation))

        return sentinel

    monkeypatch.setattr(Catalogue, "get_resource", staticmethod(fake_get_resource))

    async def scenario() -> None:
        result = await Public.get(f"https://open.spotify.com/{resource_kind}/resource-id")

        assert result is sentinel

    asyncio.run(scenario())

    assert calls == [(f"spotify:{resource_kind}:resource-id", operation)]


def test_get_accepts_legacy_podcast_kind_alias(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[Any] = []

    async def query(self: Queries, operation: str, variables: dict[str, Any]):
        calls.append(variables["uri"])

        return ObjectDict(
            {
                "podcastUnionV2": {
                    "__typename": "Podcast",
                    "name": "Show",
                    "uri": variables["uri"],
                }
            }
        )

    monkeypatch.setattr(Queries, "query", query)

    result = asyncio.run(Public.get("legacy-show-id", kind="podcast"))

    assert result.name == "Show"
    assert calls == ["spotify:show:legacy-show-id"]


def test_get_podcast_accepts_bare_show_id(monkeypatch: pytest.MonkeyPatch) -> None:
    async def query(self: Queries, operation: str, variables: dict[str, Any]):
        assert variables["uri"] == "spotify:show:show-id"

        return ObjectDict(
            {
                "podcastUnionV2": {
                    "__typename": "Podcast",
                    "name": "Show",
                    "uri": variables["uri"],
                }
            }
        )

    monkeypatch.setattr(Queries, "query", query)

    assert asyncio.run(Public.get_podcast("show-id")).name == "Show"


def test_search_fetches_all_categories_in_one_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeQueries()

    monkeypatch.setattr(public_module, "Queries", Mock(return_value=fake))

    result = asyncio.run(
        Public.search(
            "all categories",
            types=(
                "track",
                "album",
                "artist",
                "playlist",
                "podcast",
                "audiobook",
                "episode",
                "author",
                "genre",
                "user",
            ),
        )
    )

    assert len(result.requested_types) == 10
    assert len(fake.calls) == 1


@pytest.mark.parametrize(
    ("resource_kind", "method_name"),
    [
        ("album", "get_album"),
        ("artist", "get_artist"),
        ("episode", "get_podcast_episode"),
    ],
)
def test_get_dispatches_typed_resources(
    monkeypatch: pytest.MonkeyPatch,
    resource_kind: str,
    method_name: str,
) -> None:
    calls: list[str] = []
    sentinel = object()

    async def fake_get(uri: str) -> Any:
        calls.append(uri)

        return sentinel

    monkeypatch.setattr(Catalogue, method_name, staticmethod(fake_get))

    async def scenario() -> None:
        result = await Public.get(f"https://open.spotify.com/{resource_kind}/resource-id?si=share")

        assert result is sentinel

    asyncio.run(scenario())

    assert calls == [f"spotify:{resource_kind}:resource-id"]
