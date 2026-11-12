"""Tests for centralized Spotify resource and search operation metadata."""

from __future__ import annotations

from spotapi.operations import (
    READ_OPERATIONS,
    SEARCH_DESKTOP_SECTIONS,
    SEARCH_RESULT_FIELDS,
    Operations,
    SearchOptions,
    normalize_resource_kind,
    normalize_search_kind,
)


def test_retry_permission_is_explicit_and_excludes_mutations() -> None:
    assert Operations.QUERY_BOOK_CHAPTERS in READ_OPERATIONS
    assert Operations.SEARCH_DESKTOP in READ_OPERATIONS
    assert Operations.ADD_TO_PLAYLIST not in READ_OPERATIONS
    assert Operations.ADD_TO_LIBRARY not in READ_OPERATIONS
    assert Operations.FOLLOW_USERS not in READ_OPERATIONS
    assert "unknownOperation" not in READ_OPERATIONS


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
    assert set(SEARCH_DESKTOP_SECTIONS) == set(SEARCH_RESULT_FIELDS)


def test_search_options_keep_python_names_separate_from_wire_keys() -> None:
    options = SearchOptions(limit=12, include_audiobooks=True, include_pre_releases=True)
    variables = options.to_variables()

    assert variables == {
        "limit": 12,
        "numberOfTopResults": 20,
        "includeAudiobooks": True,
        "includeArtistHasConcertsField": False,
        "includePreReleases": True,
        "includeAlbumPreReleases": False,
        "includeAuthors": False,
        "includeEpisodeContentRatingsV2": False,
    }
    variables["limit"] = 1
    assert options.limit == 12
    assert options.to_variables()["limit"] == 12


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
