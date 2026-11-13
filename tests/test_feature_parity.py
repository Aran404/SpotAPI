"""Contracts for additional discovery, transcript, export and batch surfaces."""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import AsyncClient, Catalogue, ResponseCache, fetch_many, to_dict
from spotapi.catalogue import _discovered_playlists
from spotapi.charts import chart, list_charts
from spotapi.datastruct import ObjectDict
from spotapi.embeds import Embed
from spotapi.models import Concert, CoverColors, Transcript
from spotapi.operations import Operations
from spotapi.queries import Queries
from spotapi.resources import parse_spotify_image, parse_spotify_resource
from spotapi.transcripts import Transcripts
from spotapi.types import BaseClientError, HTTPError


def discovered_response(items: object) -> ObjectDict:
    return ObjectDict(
        {
            "artistUnion": {
                "uri": "spotify:artist:artist",
                "relatedContent": {"discoveredOnV2": {"items": items}},
            }
        }
    )


def test_discovered_on_preserves_order_duplicates_and_unavailable_slots() -> None:
    playlist = {"__typename": "Playlist", "uri": "spotify:playlist:one", "name": "One"}
    result = _discovered_playlists(
        discovered_response(
            [{"data": playlist}, {"data": {"__typename": "GenericError"}}, {"data": playlist}]
        )
    )
    assert [item.uri if item is not None else None for item in result] == [
        "spotify:playlist:one",
        None,
        "spotify:playlist:one",
    ]
    assert _discovered_playlists(discovered_response([])) == ()


@pytest.mark.parametrize(
    "items",
    [
        None,
        {},
        [None],
        [{"data": None}],
        [{"data": {"__typename": "UnrecognizedError"}}],
        [{"data": {"__typename": "Playlist", "uri": "spotify:track:one", "name": "One"}}],
        [{"data": {"__typename": "Playlist", "uri": "spotify:playlist:", "name": "One"}}],
        [{"data": {"__typename": "Playlist", "uri": "spotify:playlist:one"}}],
    ],
)
def test_discovered_on_rejects_missing_or_changed_payloads(items: object) -> None:
    with pytest.raises(BaseClientError):
        _discovered_playlists(discovered_response(items))


async def test_discovered_on_normalizes_input_and_checks_artist_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = AsyncMock(return_value=discovered_response([]))
    monkeypatch.setattr(Queries, "query", query)
    async with Catalogue(queries=Queries()) as spotify:
        assert await spotify.get_artist_discovered_on("artist") == ()
        query.assert_awaited_once_with(
            Operations.QUERY_ARTIST_DISCOVERED_ON, {"uri": "spotify:artist:artist"}
        )
        with pytest.raises(BaseClientError):
            await spotify.get_artist_discovered_on("different")


def test_transcript_retains_music_cues_and_omits_speaker_headings() -> None:
    transcript = Transcript.from_dict(
        {
            "language": "en",
            "section": [
                {"title": {"title": "Speaker"}},
                {"text": {"sentence": {"text": "Hello", "startMs": "100"}}},
                {"fallback": {"sentence": {"text": "[Music]", "startMs": 200}}},
            ],
        }
    )
    assert [(line.start_time_ms, line.text) for line in transcript.lines] == [
        (100, "Hello"),
        (200, "[Music]"),
    ]
    assert transcript.language == "en" and transcript.is_auto_generated is None


@pytest.mark.parametrize(
    "sections",
    [None, [{"text": {"sentence": {"text": "bad", "startMs": True}}}], [{"unknown": 1}]],
)
def test_transcript_rejects_missing_or_malformed_cues(sections: object) -> None:
    with pytest.raises(BaseClientError):
        Transcript.from_dict({"section": sections})


def test_embed_discards_session_tokens_and_verifies_identity() -> None:
    resource = parse_spotify_resource("spotify:track:abc")
    entity = {
        "uri": resource.uri,
        "name": "Example",
        "duration": 1200,
        "audioPreview": {"url": "https://p.scdn.co/preview.mp3"},
    }
    body = {
        "props": {
            "pageProps": {
                "state": {
                    "data": {"entity": entity},
                    "session": {"accessToken": "test-only-token"},
                }
            }
        }
    }
    html = "<script type='application/json' id='__NEXT_DATA__'>" + json.dumps(body) + "</script>"
    embed = Embed.from_html(html, resource)
    assert embed.name == "Example" and embed.duration_ms == 1200
    assert "test-only-token" not in json.dumps(to_dict(embed))
    with pytest.raises(BaseClientError, match="different"):
        Embed.from_html(html, parse_spotify_resource("spotify:track:other"))


def test_palette_validation_preserves_fallback_state() -> None:
    body = {
        "extractedColors": [
            {
                key: {"hex": "#12AB34", "isFallback": False}
                for key in ("colorRaw", "colorDark", "colorLight")
            }
        ]
    }
    result = CoverColors.from_dict(body)
    assert result.raw == "#12AB34" and result.is_fallback is False
    body["extractedColors"][0]["colorRaw"]["hex"] = "#invalid"
    with pytest.raises(BaseClientError):
        CoverColors.from_dict(body)


def test_concert_retains_optional_data_without_inventing_location() -> None:
    concert = Concert.from_dict({"uri": "spotify:concert:abc", "title": "A show"})
    assert concert.city is None and concert.start_date is None and concert.artists == ()


def test_chart_shortcuts_are_playlist_identities() -> None:
    assert chart("top-50-global") in list_charts()
    assert chart("top-50-global").uri.startswith("spotify:playlist:")
    with pytest.raises(ValueError, match="Unknown chart"):
        chart("invented-chart")


def test_cache_returns_independent_values_and_separates_namespaces(tmp_path: Path) -> None:
    cache = ResponseCache(tmp_path)
    key = cache.key("getTrack", {"uri": "spotify:track:a"}, "en|direct")
    assert key != cache.key("getTrack", {"uri": "spotify:track:a"}, "ja|direct")
    cache.put(key, ObjectDict({"track": {"name": "Original"}}))
    first = cache.get(key)
    assert first is not None
    first["track"]["name"] = "Changed"
    second = ResponseCache(tmp_path).get(key)
    assert second is not None and second["track"]["name"] == "Original"
    assert list(tmp_path.glob("*.tmp")) == []


def test_cache_expiry_and_corruption_are_misses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cache = ResponseCache(tmp_path, ttl=10)
    monkeypatch.setattr("spotapi.cache.time.time", lambda: 100)
    cache.put("a" * 64, ObjectDict({"name": "Example"}))
    monkeypatch.setattr("spotapi.cache.time.time", lambda: 111)
    assert cache.get("a" * 64) is None
    (tmp_path / ("b" * 64 + ".json")).write_text("not JSON")
    assert cache.get("b" * 64) is None


def test_authenticated_catalogues_cannot_enable_response_caching() -> None:
    with pytest.raises(ValueError, match="anonymous"):
        Catalogue(Mock(spec=AsyncClient), cache=ResponseCache())


def test_json_export_handles_dates_and_rejects_unsupported_values() -> None:
    assert to_dict({"date": date(2026, 1, 2), "items": (1, 2)}) == {
        "date": "2026-01-02",
        "items": [1, 2],
    }
    for value in (object(), float("nan"), {1: "bad key"}):
        with pytest.raises(TypeError):
            to_dict(value)


async def test_batch_preserves_duplicates_errors_and_concurrency() -> None:
    active = peak = 0

    async def read(value: str) -> str:
        nonlocal active, peak
        active += 1
        peak = max(active, peak)
        try:
            await asyncio.sleep(0)
            if value == "bad":
                raise ValueError("bad input")
            return value.upper()
        finally:
            active -= 1

    result = await fetch_many(["a", "bad", "a", "b"], read, concurrency=2)
    assert [item.index for item in result] == [0, 1, 2, 3]
    assert result[0].unwrap() == result[2].unwrap() == "A"
    assert not result[1].ok and result[3].unwrap() == "B"
    with pytest.raises(ValueError, match="bad input"):
        result[1].unwrap()
    assert peak == 2 and active == 0


async def test_batch_cancellation_is_not_an_item_error() -> None:
    async def cancelled(value: str) -> str:
        raise asyncio.CancelledError()

    # TaskGroup treats a cancelled worker as cancellation, not an ordinary error.
    with pytest.raises(asyncio.CancelledError):
        await fetch_many(["a"], cancelled)


async def test_transcript_requests_explicit_json_with_managed_authorization() -> None:
    client = Mock(spec=AsyncClient)
    client.get = AsyncMock(return_value=Mock(json=ObjectDict({"section": []})))
    assert (await Transcripts(client).get("episode")).lines == ()
    assert client.get.await_args is not None
    assert client.get.await_args.kwargs["authorized"] is True
    assert client.get.await_args.kwargs["headers"] == {"accept": "application/json"}


async def test_discovery_operations_have_explicit_variables_and_typed_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = AsyncMock(
        side_effect=[
            ObjectDict(
                {
                    "seoRecommendedTrackAlbum": {
                        "items": [{"data": {"uri": "spotify:album:a", "name": "Album"}}]
                    }
                }
            ),
            ObjectDict({"concerts": {"concerts": {"items": []}}}),
        ]
    )
    monkeypatch.setattr(Queries, "query", query)
    async with Catalogue(queries=Queries()) as spotify:
        assert (await spotify.get_similar_albums("track"))[0].name == "Album"
        assert await spotify.get_artist_events("artist") == ()
    assert query.await_args_list[0].args == (
        Operations.SIMILAR_ALBUMS_BASED_ON_THIS_TRACK,
        {"uri": "spotify:track:track", "limit": 10},
    )
    assert query.await_args_list[1].args == (
        Operations.ARTIST_CONCERTS,
        {"artistUri": "spotify:artist:artist", "includeNearby": False},
    )


async def test_lookup_does_not_hide_authentication_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        Catalogue, "get", AsyncMock(side_effect=HTTPError("Unauthorized", status_code=401))
    )
    async with Catalogue(queries=Queries()) as spotify:
        with pytest.raises(HTTPError):
            await spotify.lookup("spotify:track:abc")


@pytest.mark.parametrize(
    "error", [HTTPError("Unavailable", status_code=503), BaseClientError("Changed contract")]
)
async def test_lookup_does_not_downgrade_a_borrowed_query_scope(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    monkeypatch.setattr(Catalogue, "get", AsyncMock(side_effect=error))
    embed = AsyncMock()
    monkeypatch.setattr("spotapi.catalogue.get_embed", embed)
    async with Catalogue(queries=Queries()) as spotify:
        with pytest.raises(type(error)):
            await spotify.lookup("spotify:track:abc")
    embed.assert_not_awaited()


async def test_lookup_can_fall_back_in_an_owned_anonymous_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(Catalogue, "get", AsyncMock(side_effect=BaseClientError("Changed")))
    embed = AsyncMock()
    monkeypatch.setattr("spotapi.catalogue.get_embed", embed)
    async with Catalogue(proxy="http://proxy.test:8080") as spotify:
        assert await spotify.lookup("spotify:track:abc") is embed.return_value
    embed.assert_awaited_once_with("spotify:track:abc", proxy="http://proxy.test:8080")


@pytest.mark.parametrize(
    "source",
    [
        "spotify:image:abc",
        "https://i.scdn.co/image/abc",
        "https://image-cdn-ak.spotifycdn.com/image/abc?size=3",
    ],
)
def test_image_identity_accepts_both_current_spotify_cdn_families(source: str) -> None:
    assert parse_spotify_image(source) == "spotify:image:abc"


@pytest.mark.parametrize(
    "source",
    [
        "https://i.scdn.co.evil.test/image/abc",
        "https://user@i.scdn.co/image/abc",
        "https://image-cdn-ak.spotifycdn.com/image/a/b",
    ],
)
def test_image_identity_rejects_foreign_or_embedded_path_segments(source: str) -> None:
    with pytest.raises(ValueError):
        parse_spotify_image(source)


def test_preview_cli_registers_optional_tagging_flag() -> None:
    from spotapi.cli import _parser

    args = _parser().parse_args(
        ["download", "preview", "spotify:track:abc", "--output", "preview.mp3"]
    )
    assert args.embed_cover is False


def test_json_export_does_not_serialize_exception_messages() -> None:
    assert to_dict(HTTPError("credential-bearing test text", status_code=401)) == {
        "type": "HTTPError",
        "status_code": 401,
    }


def test_model_shaped_dates_round_trip_without_returning_strings() -> None:
    from dataclasses import dataclass

    from spotapi import from_dict

    @dataclass
    class Dated:
        day: date

    value = Dated(date(2026, 11, 12))
    restored = from_dict(Dated, to_dict(value))
    assert restored == value and isinstance(restored.day, date)


def test_generic_resource_decoder_rejects_invalid_kind_literals() -> None:
    from spotapi import from_dict
    from spotapi.resources import SpotifyResource

    with pytest.raises(TypeError, match="literal"):
        from_dict(
            SpotifyResource,
            {
                "kind": "invented",
                "id": "a",
                "uri": "spotify:invented:a",
                "url": "https://open.spotify.com/invented/a",
            },
        )


def test_generic_decoder_does_not_treat_error_metadata_as_an_exception() -> None:
    from spotapi import BatchItem, from_dict

    with pytest.raises(TypeError):
        from_dict(BatchItem, {"index": 0, "value": "bad", "error": {"type": "ValueError"}})
