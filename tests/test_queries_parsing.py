"""Regression tests for shared typed and raw search result parsing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.operations import Operations
from spotapi.v2.queries import Queries
from spotapi.v2.types import BaseClientError


@dataclass(slots=True)
class _Sample:
    id: str
    name: str


def _object(mapping: dict[str, Any]) -> ObjectDict:
    """Construct an ObjectDict for tests using the package's normal mapping API."""
    return ObjectDict(mapping)


def test_extract_data_supports_direct_and_wrapped_payloads() -> None:
    direct = _object({"data": _object({"id": "1", "name": "direct"})})
    wrapped = _object({"entity": _object({"data": _object({"id": "2", "name": "wrapped"})})})

    assert Queries.extract_data(direct)["id"] == "1"
    assert Queries.extract_data(wrapped)["id"] == "2"


def test_parse_items_deserializes_typed_models(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_from_dict(typ: type[Any], payload: ObjectDict) -> Any:
        return typ(**payload)

    monkeypatch.setattr("spotapi.v2.queries.from_dict", fake_from_dict)

    page = _object(
        {
            "items": [
                _object({"data": _object({"id": "1", "name": "first"})}),
                _object({"data": _object({"id": "2", "name": "second"})}),
            ]
        }
    )

    results = Queries.parse_items(page, _Sample, Operations.SEARCH_TRACKS)

    assert results == [_Sample("1", "first"), _Sample("2", "second")]


def test_parse_items_skips_null_and_incomplete_search_hits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_from_dict(typ: type[Any], payload: ObjectDict) -> Any:
        return typ(**payload)

    monkeypatch.setattr("spotapi.v2.queries.from_dict", fake_from_dict)

    page = _object(
        {
            "items": [
                _object({"data": None}),
                _object({"data": _object({"id": "missing-name"})}),
                _object({"data": _object({"id": "ok", "name": "valid"})}),
            ]
        }
    )

    assert Queries.parse_items(page, _Sample, Operations.SEARCH_TRACKS, skip_invalid=True) == [
        _Sample("ok", "valid")
    ]


def test_parse_items_reports_invalid_page_shape() -> None:
    with pytest.raises(BaseClientError, match="missing search items"):
        Queries.parse_items(_object({}), _Sample, Operations.SEARCH_TRACKS)


def test_parse_raw_items_returns_separate_object_dict_collection() -> None:
    first = _object({"id": "1", "name": "first"})
    page = _object(
        {
            "items": [
                _object({"data": first}),
                _object({"data": None}),
            ]
        }
    )

    assert Queries.parse_raw_items(page, Operations.SEARCH_AUDIOBOOKS) == [first]


def test_parse_raw_items_rejects_non_object_entries() -> None:
    page = _object({"items": ["not-an-object"]})

    with pytest.raises(BaseClientError, match="invalid search item"):
        Queries.parse_raw_items(page, Operations.SEARCH_AUDIOBOOKS)


def test_parse_items_can_skip_deserialization_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_from_dict(typ: type[Any], payload: ObjectDict) -> Any:
        raise ValueError("bad entity")

    monkeypatch.setattr("spotapi.v2.queries.from_dict", fail_from_dict)

    page = _object({"items": [{"data": {"id": "1", "name": "broken"}}]})

    assert Queries.parse_items(page, _Sample, Operations.SEARCH_TRACKS, skip_invalid=True) == []

    with pytest.raises(ValueError, match="bad entity"):
        Queries.parse_items(page, _Sample, Operations.SEARCH_TRACKS, skip_invalid=False)


def test_parse_raw_items_can_skip_non_mapping_entries() -> None:
    page = _object(
        {
            "items": [
                "broken",
                {"data": {"id": "1", "name": "valid"}},
            ]
        }
    )

    assert Queries.parse_raw_items(page, Operations.SEARCH_AUDIOBOOKS, skip_invalid=True) == [
        _object({"id": "1", "name": "valid"})
    ]
