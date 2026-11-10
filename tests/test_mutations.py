"""Mutation safety and identifier behavior without touching a Spotify library."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.playlist import Playlist, PlaylistHandler, _as_uri
from spotapi.v2.query import QueryClient
from spotapi.v2.session import AuthSession
from spotapi.v2.types import PlaylistError


@pytest.mark.parametrize(
    "value", ["abc", "spotify:track:abc", "https://open.spotify.com/track/abc?si=share"]
)
def test_track_inputs_are_consistent(value: str) -> None:
    assert _as_uri("track", value) == "spotify:track:abc"


def test_track_inputs_reject_another_resource_kind() -> None:
    with pytest.raises(ValueError, match="Resource is a album"):
        _as_uri("track", "spotify:album:abc")


@pytest.mark.parametrize(
    "operation,safe",
    [("addToPlaylist", False), ("unknownOperation", False), ("searchDesktop", True)],
)
async def test_pathfinder_models_retry_safety(operation: str, safe: bool) -> None:
    options: list[dict[str, Any]] = []

    async def post(url: str, **kwargs: Any):
        options.append(kwargs)

        return SimpleNamespace(json=ObjectDict({"data": {"ok": True}}))

    session = Mock(
        spec=AuthSession,
        session=Mock(query_hash=Mock(return_value="a" * 64)),
        client=SimpleNamespace(post=post),
        authorized_headers={},
    )

    await QueryClient(session).pathfinder_query({}, operation)

    assert options[0]["retry_safe"] is safe


async def test_playlist_mutation_uses_exactly_one_attempt() -> None:
    calls: list[dict[str, Any]] = []

    async def post(url: str, **kwargs: Any):
        calls.append(kwargs)

        return SimpleNamespace(json=ObjectDict({"revision": "revision"}))

    session = Mock(spec=AuthSession, client=SimpleNamespace(post=post), authorized_headers={})
    handler = PlaylistHandler(session)

    await handler._post("https://example.test/mutation", {})

    assert calls[0]["max_attempts"] == 1


async def test_removed_tracks_do_not_break_uid_resolution() -> None:
    playlist = Playlist(Mock(spec=AuthSession), "playlist-id")

    async def pages(*args: object, **kwargs: Any):
        yield ObjectDict(
            {
                "items": [
                    {"uid": "removed", "itemV2": {"data": None}},
                    {
                        "uid": "occurrence",
                        "itemV2": {"data": {"uri": "spotify:track:abc"}},
                    },
                ]
            }
        )

    playlist.ph.qc = Mock(spec=QueryClient, paginate_query=pages)

    assert await playlist._resolve_uids({"spotify:track:abc"}) == ["occurrence"]


async def test_exact_occurrence_removal_deduplicates_without_reading_playlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = AsyncMock(
        return_value=ObjectDict(
            {"removeItemsFromPlaylist": {"__typename": "RemoveItemsFromPlaylistPayload"}}
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    playlist = Playlist(Mock(spec=AuthSession), "playlist-id")
    await playlist.remove_occurrences("second-copy", "second-copy")
    query.assert_awaited_once_with(
        {"uids": ["second-copy"], "playlistUri": "spotify:playlist:playlist-id"},
        "removeFromPlaylist",
        max_attempts=1,
    )
    with pytest.raises(ValueError):
        await playlist.remove_occurrences("")


@pytest.mark.parametrize("remove", [False, True])
@pytest.mark.parametrize("typename", ["NotFound", "GenericError", "PermissionDenied", None])
async def test_playlist_error_unions_never_report_mutation_success(
    monkeypatch: pytest.MonkeyPatch, remove: bool, typename: str | None
) -> None:
    field = "removeItemsFromPlaylist" if remove else "addItemsToPlaylist"
    query = AsyncMock(return_value=ObjectDict({field: {"__typename": typename}}))
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    playlist = Playlist(Mock(spec=AuthSession), "playlist-id")

    with pytest.raises(PlaylistError):
        if remove:
            await playlist.remove_occurrences("occurrence")
        else:
            await playlist.add_tracks("track")

    query.assert_awaited_once()
    assert query.call_args.kwargs["max_attempts"] == 1


async def test_playlist_add_accepts_verified_success_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    query = AsyncMock(
        return_value=ObjectDict(
            {"addItemsToPlaylist": {"__typename": "AddItemsToPlaylistPayload"}}
        )
    )
    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    await Playlist(Mock(spec=AuthSession), "playlist-id").add_tracks("track")
    query.assert_awaited_once()


async def test_playlist_edit_uses_sync_commit_and_explicit_description_clear(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    post = AsyncMock(return_value=ObjectDict({"revision": "new-revision"}))
    monkeypatch.setattr(PlaylistHandler, "_post", post)
    playlist = Playlist(Mock(spec=AuthSession), "playlist-id")
    await playlist.edit(name="New name", description="")
    body = post.call_args.args[1]
    attributes = body["deltas"][0]["ops"][0]["updateListAttributes"]["newAttributes"]
    assert body["wantSyncResult"] is True
    assert attributes["values"]["name"] == "New name"
    assert attributes["noValue"] == ["LIST_DESCRIPTION"]
    assert "description" not in attributes["values"]
    with pytest.raises(ValueError):
        await playlist.edit(name=" ")


async def test_fresh_playlist_metadata_bypasses_delayed_graphql_state() -> None:
    get = AsyncMock(
        return_value=SimpleNamespace(
            json=ObjectDict(
                {
                    "attributes": {"name": "Fresh name", "description": ""},
                    "revision": "fresh-revision",
                    "length": 0,
                    "ownerUsername": "owner",
                }
            )
        )
    )
    session = Mock(spec=AuthSession, client=SimpleNamespace(get=get), authorized_headers={})
    playlist = Playlist(session, "playlist-id")
    data = await playlist.get(fresh=True)
    assert data.name == "Fresh name" and data.total_count == 0
    assert data.description == "" and data.revision_id == "fresh-revision"
    assert get.call_args.args[0].endswith("/playlist/v2/playlist/playlist-id")
