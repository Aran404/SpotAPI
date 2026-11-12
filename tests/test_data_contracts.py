"""Real JSON key spelling, partial models, and cache boundaries."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from pathlib import Path

import pytest

from spotapi.datastruct import ObjectDict
from spotapi.models.catalogue import Track, from_dict
from spotapi.models.catalogue.common import SquareCoverImage
from spotapi.operations import Operations
from spotapi.queries import Queries
from spotapi.session import QueryCache
from spotapi.utils import timed_cache


@pytest.mark.parametrize("wrapped", [False, True])
def test_decoder_reads_graphql_metadata_without_rewriting_keys(wrapped: bool) -> None:
    payload = {"__typename": "SquareCoverImage"}
    data = ObjectDict(payload) if wrapped else payload

    assert from_dict(SquareCoverImage, data)._typename == "SquareCoverImage"
    assert data == payload


@dataclass
class _Metadata:
    _typename: str


def test_search_preflight_and_decoder_accept_the_same_metadata_alias() -> None:
    page = ObjectDict({"items": [{"data": {"__typename": "Track"}}]})

    assert Queries.parse_items(page, _Metadata, Operations.SEARCH_TRACKS) == [_Metadata("Track")]


@dataclass
class _Collections:
    pair: tuple[int, str]
    labels: set[str]
    numbers: frozenset[int]
    counts: dict[str, int]
    choice: int | str | None


def test_decoder_preserves_declared_collection_and_union_types() -> None:
    value = from_dict(
        _Collections,
        {
            "pair": [1, "one"],
            "labels": ["a", "a"],
            "numbers": [1, 2],
            "counts": {"a": 2},
            "choice": None,
        },
    )
    assert value == _Collections((1, "one"), {"a"}, frozenset({1, 2}), {"a": 2}, None)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [("pair", [1], ValueError), ("numbers", [True], TypeError), ("choice", [], TypeError)],
)
def test_decoder_reports_invalid_nested_collection_values(
    field: str, value: object, error: type[Exception]
) -> None:
    payload: dict[str, object] = {
        "pair": [1, "one"],
        "labels": [],
        "numbers": [],
        "counts": {},
        "choice": None,
        field: value,
    }
    with pytest.raises(error, match=field):
        from_dict(_Collections, payload)


def test_object_dict_preserves_colliding_keys_through_mutations() -> None:
    source = {
        "items": [{"name": "track"}],
        "_items": "original underscore",
        "__items": 3,
        "get": 4,
    }
    data = ObjectDict(source)

    assert data._items[0].name == "track"
    assert data.__items == "original underscore"
    assert data.___items == 3
    assert data._get == 4
    assert callable(data.items) and callable(data.get)
    data.update({"items": [{"name": "updated"}]})

    data |= {"extra": {"items": []}}

    assert data["items"][0].name == "updated"
    assert data.extra._items == []
    assert data.setdefault("new", {"items": []})._items == []
    assert json.loads(data.to_json()) == data.to_dict()
    assert data.to_dict()["_items"] == source["_items"]
    data.__items = "changed"

    assert data["_items"] == "changed"
    del data.__items

    assert "_items" not in data


def test_search_decoder_uses_original_items_even_when_underscore_key_exists() -> None:
    page = ObjectDict(
        {
            "items": [{"data": {"id": "id", "name": "Song", "uri": "spotify:track:id"}}],
            "_items": [],
        }
    )
    tracks = Queries.parse_items(page, Track, Operations.SEARCH_DESKTOP)

    assert len(tracks) == 1
    assert repr(tracks[0]) == "<Track id='id' name='Song' artists=''>"


@pytest.mark.parametrize("field,value", [("id", 12), ("name", None), ("uri", False)])
def test_model_rejects_invalid_required_values(field: str, value: object) -> None:
    payload = {"id": "id", "name": "Song", "uri": "spotify:track:id", field: value}

    with pytest.raises(TypeError):
        from_dict(Track, payload)


def test_optional_model_fields_may_be_missing() -> None:
    track = from_dict(Track, {"id": "id", "name": "Song", "uri": "spotify:track:id"})

    assert track.duration is None
    assert track.artists is None
    assert "Song" in repr(track)


def test_query_cache_validates_expiry_shape_and_size(tmp_path: Path) -> None:
    cache = QueryCache(tmp_path / "queries.json")
    valid = {"searchDesktop": "a" * 64}

    cache.save(valid)

    assert cache.load() == valid
    assert list(tmp_path.iterdir()) == [cache.path]
    old = time.time() - 86401

    os.utime(cache.path, (old, old))

    assert cache.load() is None
    cache.path.write_text(json.dumps({"query": "wrong hash"}))

    assert cache.load() is None
    cache.path.write_text("x" * 1_048_577)

    assert cache.load() is None


async def test_async_cache_bounds_ttl_and_failure_recovery() -> None:
    calls = 0

    @timed_cache(maxsize=2)
    async def cached(number: int) -> int:
        nonlocal calls
        calls += 1

        if number < 0:
            raise ValueError("invalid")

        return number

    assert await cached(1) == await cached(1) == 1
    assert calls == 1

    await cached(2)
    await cached(3)
    await cached(1)

    assert calls == 4

    for _ in range(2):
        with pytest.raises(ValueError):
            await cached(-1)

    assert calls == 6
    cached.cache_clear()
    await cached(1)

    assert calls == 7


def test_palette_roles_share_color_contract_without_changing_export_shape() -> None:
    from dataclasses import asdict

    from spotapi._decoding import from_dict
    from spotapi.models.catalogue.common import RGBA, ContrastPalette, ExtractedColorSet

    color = {"alpha": 255, "blue": 3, "green": 2, "red": 1}
    body = {
        "encoreBaseSetTextColor": color,
        "highContrast": {"textBase": color},
        "higherContrast": {"backgroundBase": color},
        "minContrast": {"textSubdued": color},
    }
    result = from_dict(ExtractedColorSet, body)

    assert isinstance(result.encore_base_set_text_color, RGBA)
    for palette in (result.high_contrast, result.higher_contrast, result.min_contrast):
        assert isinstance(palette, ContrastPalette)
    assert asdict(result)["high_contrast"]["text_base"] == color
    assert result.high_contrast is not None
    assert result.high_contrast.background_base is None
