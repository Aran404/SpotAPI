"""Tests for centralized Spotify resource and search operation metadata."""

from __future__ import annotations

from spotapi.v2.operations import (
    SEARCH_DESKTOP_SECTIONS,
    SEARCH_RAW_OPERATIONS,
    SEARCH_RESULT_FIELDS,
    normalize_resource_kind,
    normalize_search_kind,
)


def test_resource_kind_aliases_are_canonicalized() -> None:
    assert normalize_resource_kind("podcast") == "show"
    assert normalize_resource_kind("SHOW") == "show"
    assert normalize_resource_kind("track") == "track"


def test_search_kind_aliases_are_canonicalized() -> None:
    assert normalize_search_kind("tracks") == "track"
    assert normalize_search_kind("Artists") == "artist"
    assert normalize_search_kind("show") == "podcast"
    assert normalize_search_kind("books") == "audiobook"


def test_every_search_category_has_operation_and_result_field() -> None:
    categories = set(SEARCH_DESKTOP_SECTIONS) | set(SEARCH_RAW_OPERATIONS)

    assert categories == set(SEARCH_RESULT_FIELDS)
    assert set(SEARCH_DESKTOP_SECTIONS).isdisjoint(SEARCH_RAW_OPERATIONS)


def test_unknown_resource_and_search_kinds_are_rejected() -> None:
    try:
        normalize_resource_kind("local")
    except ValueError as error:
        assert "Unsupported Spotify resource type" in str(error)
    else:
        raise AssertionError("unknown resource kind must be rejected")

    try:
        normalize_search_kind("unknown")
    except ValueError as error:
        assert "Unsupported Spotify search type" in str(error)
    else:
        raise AssertionError("unknown search kind must be rejected")
