"""Regression tests for ``preReleaseEndDateTime`` objects in album payloads.

Spotify returns this field as ``{"isoString": ..., "precision": ...}`` even when
``isPreRelease`` is false. It once failed with ``getAlbum: failed to deserialize
AlbumDetails: AlbumDetails.pre_release_end_date_time: value does not match
str | None``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from spotapi.datastruct import ObjectDict
from spotapi.models.catalogue import Album, AlbumDetails, from_dict
from spotapi.models.catalogue.common import ReleaseDate
from spotapi.operations import Operations
from spotapi.queries import Queries

ALBUM_URI = "spotify:album:3LUcDBe7DZDExhHbZEQchk"
FIXTURE = Path(__file__).parent / "fixtures" / "catalogue" / "get_album_pre_release_end_date.json"


def _album_response() -> dict[str, Any]:
    """Load the sanitized, trimmed getAlbum response for the Nytt Land album."""
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


async def _get_album(response: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> AlbumDetails:
    async def direct_query(self: Queries, uri: str, /, operation: Operations) -> ObjectDict:
        assert (uri, operation) == (ALBUM_URI, Operations.GET_ALBUM)

        return ObjectDict(response)

    monkeypatch.setattr(Queries, "direct_query", direct_query)

    return await Queries().resource(ALBUM_URI, Operations.GET_ALBUM, AlbumDetails)


async def test_get_album_decodes_object_pre_release_end_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    album = await _get_album(_album_response(), monkeypatch)

    assert album.is_pre_release is False
    assert album.pre_release_end_date_time == ReleaseDate(
        iso_string="2026-02-20T05:00:00Z", precision="MINUTE"
    )
    assert album.name == "Aba Khan"
    assert [track.name for track in album.tracks] == ["Aba Khan", "Taiga"]


@pytest.mark.parametrize("precision", ["DAY", "MINUTE"])
async def test_get_album_accepts_either_pre_release_precision(
    precision: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = _album_response()
    response["albumUnion"]["preReleaseEndDateTime"] = {
        "isoString": "2026-02-20T00:00:00Z",
        "precision": precision,
    }

    album = await _get_album(response, monkeypatch)

    assert album.pre_release_end_date_time is not None
    assert album.pre_release_end_date_time.precision == precision
    assert album.pre_release_end_date_time.year == 2026


@pytest.mark.parametrize("missing", [False, True])
async def test_get_album_keeps_pre_release_end_date_optional(
    missing: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    response = _album_response()

    if missing:
        del response["albumUnion"]["preReleaseEndDateTime"]
    else:
        response["albumUnion"]["preReleaseEndDateTime"] = None

    album = await _get_album(response, monkeypatch)

    assert album.pre_release_end_date_time is None


def test_album_search_hit_decodes_object_pre_release_end_date() -> None:
    """Search skips undecodable hits, so a mismatch would silently drop the album."""
    album = from_dict(
        Album,
        {
            "name": "Aba Khan",
            "uri": ALBUM_URI,
            "isAlbumPreRelease": False,
            "preReleaseEndDateTime": {"isoString": "2026-02-20T05:00:00Z", "precision": "MINUTE"},
        },
    )

    assert album.pre_release_end_date_time == ReleaseDate(
        iso_string="2026-02-20T05:00:00Z", precision="MINUTE"
    )
