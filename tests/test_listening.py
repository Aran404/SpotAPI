"""Library batching and the dated identity traits returned by Spotify recents."""

from datetime import date
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import LikedTracks, ListeningHistory
from spotapi.models import RecentItem
from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.query import QueryClient
from spotapi.v2.session import AuthSession
from spotapi.v2.types import BaseClientError

TRACK = "33XUHrCbrAW6me9ewdCZip"


async def test_library_batches_without_losing_input_order() -> None:
    library = LikedTracks(Mock(spec=AuthSession))
    query = AsyncMock(
        side_effect=[
            ObjectDict({"lookup": [{"data": {"saved": True}}] * 50}),
            ObjectDict({"lookup": [{"data": {"saved": False}}]}),
        ]
    )
    library.queries = Mock(spec=QueryClient, pathfinder_query=query)

    flags = await library.contains([TRACK] * 51)

    assert flags == (True,) * 50 + (False,)
    assert [len(call.args[0]["uris"]) for call in query.await_args_list] == [50, 1]
    assert all(call.kwargs["max_attempts"] == 1 for call in query.await_args_list)


@pytest.mark.parametrize("lookup", [[], [{"data": {"saved": "false"}}]])
async def test_library_rejects_incomplete_or_untyped_saved_flags(lookup: list[object]) -> None:
    library = LikedTracks(Mock(spec=AuthSession))
    library.queries = Mock(
        spec=QueryClient, pathfinder_query=AsyncMock(return_value=ObjectDict({"lookup": lookup}))
    )

    with pytest.raises(BaseClientError):
        await library.contains([TRACK])


async def test_library_mutations_use_native_variables_and_never_replay() -> None:
    library = LikedTracks(Mock(spec=AuthSession))
    query = AsyncMock(
        side_effect=[
            ObjectDict({"addLibraryItems": {"__typename": "AddLibraryItemsResponse"}}),
            ObjectDict({"removeLibraryItems": {"__typename": "RemoveLibraryItemsResponse"}}),
        ]
    )
    library.queries = Mock(spec=QueryClient, pathfinder_query=query)

    await library.add([f"https://open.spotify.com/track/{TRACK}"])
    await library.remove([TRACK])

    added, removed = query.await_args_list

    assert added.args[0]["libraryItemUris"] == [f"spotify:track:{TRACK}"]
    assert added.args[0]["interactionId"]
    assert removed.args == ({"libraryItemUris": [f"spotify:track:{TRACK}"]}, "removeFromLibrary")
    assert added.kwargs == removed.kwargs == {"max_attempts": 1}


@pytest.mark.parametrize("remove", [False, True])
@pytest.mark.parametrize("typename", ["NotFound", "GenericError", None])
async def test_library_error_payloads_never_report_success(
    remove: bool, typename: str | None
) -> None:
    library = LikedTracks(Mock(spec=AuthSession))
    key = "removeLibraryItems" if remove else "addLibraryItems"
    query = AsyncMock(return_value=ObjectDict({key: {"__typename": typename}}))
    library.queries = Mock(spec=QueryClient, pathfinder_query=query)
    with pytest.raises(BaseClientError, match="reconcile"):
        await (library.remove([TRACK]) if remove else library.add([TRACK]))
    query.assert_awaited_once()


def test_recent_items_parse_identity_traits_dates_and_saved_actions() -> None:
    item = RecentItem.from_dict(
        {
            "entity": {
                "data": {
                    "uri": f"spotify:track:{TRACK}",
                    "identityTrait": {
                        "name": "A song",
                        "contributors": {"items": [{"name": "An artist"}]},
                    },
                    "visualIdentityTrait": {
                        "squareCoverImage": {
                            "image": {
                                "data": {
                                    "sources": [
                                        {"width": 64, "url": "https://example.org/small"},
                                        {"width": 300, "url": "https://example.org/cover"},
                                    ]
                                }
                            }
                        }
                    },
                }
            },
            "addedAt": {"year": 2026, "month": 11, "day": 10},
            "formatListAttributes": [{"key": "recent_type_saved", "value": "true"}],
        }
    )

    assert item is not None
    assert item.name == "A song" and item.contributors == ("An artist",)
    assert item.occurred_on == date(2026, 11, 10)
    assert item.activity == "saved"
    assert item.image_url == "https://example.org/cover"


async def test_history_unwraps_list_and_ignores_unavailable_entities() -> None:
    history = ListeningHistory(Mock(spec=AuthSession))
    query = AsyncMock(
        return_value=ObjectDict(
            {
                "lists": [
                    {
                        "items": {
                            "items": [
                                {"entity": {"data": {"uri": f"spotify:track:{TRACK}"}}},
                                {"entity": {"data": {"__typename": "NotFound"}}},
                            ]
                        }
                    }
                ]
            }
        )
    )
    history.queries = Mock(spec=QueryClient, pathfinder_query=query)

    items = await history.get(limit=2, offset=4)

    assert len(items) == 1
    assert items[0].occurred_on is None and items[0].activity == "played"
    query.assert_awaited_once_with(
        {"uris": ["spotify:list:recents:page"], "limit": 2, "offset": 4},
        "recents",
        max_attempts=1,
    )
