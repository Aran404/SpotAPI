"""Typed library, affinity, profile, notification and Blend response contracts."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import (
    AsyncClient,
    Blends,
    Library,
    LikedTracks,
    ListeningStats,
    Notifications,
    Profiles,
)
from spotapi.connection import Response
from spotapi.datastruct import ObjectDict
from spotapi.discovery import recommended_tracks
from spotapi.models import BlendInvitation
from spotapi.protobuf import encode_field
from spotapi.query import QueryClient
from spotapi.session import AuthSession
from spotapi.types import BaseClientError

TRACK = "33XUHrCbrAW6me9ewdCZip"


def test_recommendations_require_track_identity_but_allow_missing_presentation() -> None:
    tracks = recommended_tracks(
        {"recommendedTracks": [{"id": TRACK, "name": "Track", "artists": [{}]}]}
    )
    assert tracks[0].uri == f"spotify:track:{TRACK}"
    assert tracks[0].album_of_track is None
    with pytest.raises(BaseClientError, match="incomplete recommended track"):
        recommended_tracks({"recommendedTracks": [{"name": "Missing ID"}]})


def response(body: Mapping[str, Any] | None = None, *, binary: bytes = b"") -> Mock:
    return Mock(spec=Response, json=ObjectDict(body) if body is not None else None, body=binary)


@pytest.fixture
def session() -> Mock:
    client = Mock(spec=AsyncClient)
    client.get = AsyncMock()
    client.post = AsyncMock()
    client.put = AsyncMock()
    return Mock(
        spec=AuthSession, client=client, authorized_headers={"authorization": "Bearer test"}
    )


async def test_saved_tracks_recover_outer_uri_and_keep_unavailable_rows(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = AsyncMock(
        return_value=ObjectDict(
            {
                "me": {
                    "library": {
                        "tracks": {
                            "items": [
                                {
                                    "addedAt": {"isoString": "2026-11-10T12:00:00Z"},
                                    "track": {
                                        "_uri": f"spotify:track:{TRACK}",
                                        "data": {
                                            "name": "A track",
                                            "albumOfTrack": {
                                                "uri": "spotify:album:album",
                                                "name": "An album",
                                            },
                                        },
                                    },
                                },
                                {
                                    "track": {
                                        "_uri": "spotify:track:unavailable",
                                        "data": {"__typename": "NotFound"},
                                    }
                                },
                            ]
                        }
                    }
                }
            }
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    items = await LikedTracks(session).get(limit=2)

    assert items[0].track is not None and items[0].track.id == TRACK
    assert items[0].track.album_of_track is not None
    assert items[0].track.album_of_track.id == "album"
    assert items[0].added_at is not None and items[0].added_at.tzinfo == UTC
    assert items[1].track is None and items[1].uri == "spotify:track:unavailable"


async def test_saved_track_pages_use_raw_page_counts_and_offsets(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    def page(offset: int, count: int) -> ObjectDict:
        return ObjectDict(
            {
                "me": {
                    "library": {
                        "tracks": {
                            "totalCount": 3,
                            "items": [
                                {
                                    "track": {
                                        "_uri": f"spotify:track:item{offset + index}",
                                        "data": {"__typename": "NotFound"},
                                    }
                                }
                                for index in range(count)
                            ],
                        }
                    }
                }
            }
        )

    query = AsyncMock(side_effect=[page(0, 2), page(2, 1)])
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    pages = [page async for page in LikedTracks(session).pages(limit=2)]

    assert [len(page) for page in pages] == [2, 1]
    assert [call.args[0]["offset"] for call in query.await_args_list] == [0, 2]


async def test_library_retains_server_filter_ids_pin_state_and_folder_depth(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = AsyncMock(
        return_value=ObjectDict(
            {
                "me": {
                    "libraryV3": {
                        "items": [
                            {
                                "item": {"_uri": "spotify:album:album", "data": {"name": "Album"}},
                                "pinned": True,
                                "pinnable": True,
                                "depth": 2,
                            }
                        ],
                        "totalCount": 1,
                        "pagingInfo": {"limit": 2, "offset": 0},
                        "availableFilters": [{"id": "Albums", "name": "Albums"}],
                        "availableSortOrders": [{"id": "Recents", "name": "Recents"}],
                    }
                }
            }
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    page = await Library(session).get(limit=2, filters=("Albums",), folder="spotify:folder:one")

    assert page.items[0].pinned and page.items[0].depth == 2
    assert page.filters[0].id == "Albums"
    assert query.await_args is not None
    assert query.await_args.args[0]["folderUri"] == "spotify:folder:one"
    assert query.await_args.args[0]["filters"] == ["Albums"]


async def test_library_rejects_bad_filter_response_and_a_single_string(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = AsyncMock(
        return_value=ObjectDict({"me": {"libraryV3": {"__typename": "InvalidFilter"}}})
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    with pytest.raises(BaseClientError):
        await Library(session).get(filters=("Unknown",))
    query.reset_mock()
    with pytest.raises(TypeError):
        await Library(session).add("spotify:album:album")
    with pytest.raises(TypeError):
        await Library(session).get(filters="Albums")
    query.assert_not_awaited()


async def test_top_content_normalizes_track_ids_and_can_omit_one_ranking(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = AsyncMock(
        return_value=ObjectDict(
            {
                "me": {
                    "profile": {
                        "topTracks": {
                            "items": [
                                {
                                    "data": {
                                        "uri": f"spotify:track:{TRACK}",
                                        "name": "Track",
                                        "albumOfTrack": None,
                                    }
                                }
                            ],
                            "totalCount": 1,
                        }
                    }
                }
            }
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    tracks = await ListeningStats(session).top_tracks(time_range="long_term", limit=1)

    assert tracks[0].id == TRACK and tracks[0].album_of_track is None
    assert query.await_args is not None
    variables = query.await_args.args[0]
    assert variables["includeTopArtists"] is False
    assert variables["topTracksInput"]["timeRange"] == "LONG_TERM"


async def test_json_and_protobuf_profile_views_share_their_verified_fields(session: Mock) -> None:
    uri = "spotify:user:listener"
    playlist = encode_field(1, "spotify:playlist:playlist") + encode_field(2, "A playlist")
    binary = (
        encode_field(1, uri)
        + encode_field(2, "Listener")
        + encode_field(4, 7)
        + encode_field(8, playlist)
        + encode_field(9, 1)
        + encode_field(400, "future field")
    )
    session.client.get.side_effect = [
        response(
            {
                "uri": uri,
                "name": "Listener",
                "followers_count": 7,
                "total_public_playlists_count": 1,
                "public_playlists": [{"uri": "spotify:playlist:playlist", "name": "A playlist"}],
            }
        ),
        response(binary=binary),
    ]
    plain = await Profiles(session).get("listener")
    compact = await Profiles(session, protobuf=True).get("listener")

    assert (plain.uri, plain.name, plain.followers_count) == (
        compact.uri,
        compact.name,
        compact.followers_count,
    )
    assert plain.public_playlists[0].uri == compact.public_playlists[0].uri
    assert (
        session.client.get.await_args_list[1].kwargs["headers"]["accept"]
        == "application/x-protobuf"
    )


async def test_protobuf_playlist_pages_stop_at_the_reported_total(session: Mock) -> None:
    row = encode_field(1, "spotify:playlist:one") + encode_field(2, "One")
    session.client.get.return_value = response(binary=encode_field(1, row) + encode_field(2, 1))
    pages = [
        page async for page in Profiles(session, protobuf=True).playlist_pages("listener", limit=2)
    ]

    assert len(pages) == 1 and pages[0].total == 1
    assert pages[0].items[0].name == "One"
    session.client.get.assert_awaited_once()


async def test_follow_lookup_requires_one_boolean_per_requested_user(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = AsyncMock(return_value=ObjectDict({"users": [{"following": "true"}]}))
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    with pytest.raises(BaseClientError):
        await Profiles(session).is_following(["listener"])


async def test_follow_and_pin_mutations_use_current_variable_names(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    query = AsyncMock(
        side_effect=[
            ObjectDict(
                {
                    "followUsers": {
                        "responses": [
                            {
                                "__typename": "FollowUserResult",
                                "username": "listener",
                                "result": True,
                            }
                        ]
                    }
                }
            ),
            ObjectDict({"pinItemInLibrary": {"pinResult": "SUCCESSFUL"}}),
        ]
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    await Profiles(session).follow("https://open.spotify.com/user/listener")
    await Library(session).pin("spotify:playlist:playlist")

    assert query.await_args_list[0].args == ({"usernames": ["listener"]}, "followUsers")
    assert query.await_args_list[1].args == (
        {"pinnableItemUri": "spotify:playlist:playlist"},
        "pinLibraryItem",
    )
    assert all(call.kwargs["max_attempts"] == 1 for call in query.await_args_list)


@pytest.mark.parametrize("remove", [False, True])
@pytest.mark.parametrize("result", [False, None])
async def test_follow_changes_reject_negative_or_missing_results(
    session: Mock, monkeypatch: pytest.MonkeyPatch, remove: bool, result: bool | None
) -> None:
    operation = "unfollowUsers" if remove else "followUsers"
    typename = "UnfollowUserResult" if remove else "FollowUserResult"
    query = AsyncMock(
        return_value=ObjectDict(
            {
                operation: {
                    "responses": [
                        {"__typename": typename, "username": "listener", "result": result}
                    ]
                }
            }
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    profiles = Profiles(session)
    with pytest.raises(BaseClientError, match="reconcile"):
        await (profiles.unfollow("listener") if remove else profiles.follow("listener"))
    query.assert_awaited_once()


@pytest.mark.parametrize("remove", [False, True])
async def test_follow_changes_match_confirmed_users_and_deduplicate_requests(
    session: Mock, monkeypatch: pytest.MonkeyPatch, remove: bool
) -> None:
    operation = "unfollowUsers" if remove else "followUsers"
    typename = "UnfollowUserResult" if remove else "FollowUserResult"
    query = AsyncMock(
        return_value=ObjectDict(
            {
                operation: {
                    "responses": [{"__typename": typename, "username": "listener", "result": True}]
                }
            }
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    profiles = Profiles(session)
    await (
        profiles.unfollow("listener", "listener")
        if remove
        else profiles.follow("listener", "listener")
    )
    assert query.call_args.args[0] == {"usernames": ["listener"]}
    query.return_value = ObjectDict(
        {
            operation: {
                "responses": [{"__typename": typename, "username": "another-user", "result": True}]
            }
        }
    )
    with pytest.raises(BaseClientError, match="reconcile"):
        await (profiles.unfollow("listener") if remove else profiles.follow("listener"))


@pytest.mark.parametrize("remove", [False, True])
@pytest.mark.parametrize("result", ["FAILED_ITEM_LIMIT_REACHED", "UNKNOWN", None])
async def test_pin_changes_require_explicit_success(
    session: Mock, monkeypatch: pytest.MonkeyPatch, remove: bool, result: str | None
) -> None:
    key = "unpinItemInLibrary" if remove else "pinItemInLibrary"
    query = AsyncMock(return_value=ObjectDict({key: {"pinResult": result}}))
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    library = Library(session)
    with pytest.raises(BaseClientError, match="reconcile"):
        await (library.unpin("playlist") if remove else library.pin("playlist"))
    query.assert_awaited_once()


async def test_notifications_keep_timezone_cursor_and_optional_images(session: Mock) -> None:
    session.client.get.return_value = response(
        {
            "notifications": [
                {
                    "id": "one",
                    "title": "New release",
                    "createdTimestamp": "2026-11-10T12:00:00.000Z",
                    "action": {"uri": "spotify:album:album", "type": "OPEN"},
                    "isNew": True,
                }
            ],
            "latestCursor": "latest",
            "forwardCursor": "older",
        }
    )
    page = await Notifications(session).get(limit=1, cursor="next")

    assert page.items[0].created_at.tzinfo == UTC
    assert page.items[0].uri == "spotify:album:album"
    assert page.items[0].image_url is None and page.items[0].is_new
    assert page.forward_cursor == "older"
    assert session.client.get.await_args_list[0].kwargs["query"]["cursor"] == "next"


async def test_blend_join_uses_the_invitation_id_and_returns_a_playlist_resource(
    session: Mock,
) -> None:
    invitation = BlendInvitation.parse(
        "https://open.spotify.com/blend/taste-match/0123456789abcdef?si=example"
    )
    session.client.put.return_value = response({"playlist_uri": "spotify:playlist:playlist"})
    playlist = await Blends(session).join(invitation)

    assert playlist.uri == "spotify:playlist:playlist"
    assert session.client.put.await_args_list[0].args[0].endswith("/join/0123456789abcdef")
    assert session.client.put.await_args_list[0].kwargs["max_attempts"] == 1


async def test_notification_badge_requires_boolean_and_explicit_acknowledgement(
    session: Mock,
) -> None:
    session.client.get.return_value = response({"userHasUnreadNotification": False})
    notifications = Notifications(session)
    assert await notifications.has_unread() is False
    session.client.post.assert_not_called()
    await notifications.mark_seen("page-cursor")
    assert session.client.post.call_args.kwargs["json"] == {"cursor": "page-cursor"}
    assert session.client.post.call_args.kwargs["max_attempts"] == 1
    session.client.get.return_value = response({"userHasUnreadNotification": "false"})
    with pytest.raises(BaseClientError):
        await notifications.has_unread()


@pytest.mark.parametrize(
    "span,wire",
    [("short_term", "SHORT_TERM"), ("medium_term", "MID_TERM"), ("long_term", "LONG_TERM")],
)
async def test_affinity_uses_spotify_time_range_enum(
    session: Mock, monkeypatch: pytest.MonkeyPatch, span: str, wire: str
) -> None:
    from typing import cast

    from spotapi.models import TimeRange

    query = AsyncMock(
        return_value=ObjectDict(
            {"me": {"profile": {"topTracks": {"items": []}, "topArtists": {"items": []}}}}
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    await ListeningStats(session).get(time_range=cast(TimeRange, span))
    assert query.call_args.args[0]["topTracksInput"]["timeRange"] == wire
