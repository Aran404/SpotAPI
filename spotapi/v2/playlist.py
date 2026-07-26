from __future__ import annotations

import time
import secrets
from typing import Any, AsyncGenerator, ClassVar, Literal
from urllib.parse import quote

from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.query import QueryClient
from spotapi.v2.session import AuthSession
from spotapi.v2.types import PlaylistError


class PlaylistHandler:
    __slots__: tuple[str, ...] = (
        "session",
        "qc",
    )

    PLAYLIST_OP_URI: ClassVar[str] = "https://spclient.wg.spotify.com/playlist/v2/playlist"
    PLAYLIST_CHANGES_URI: ClassVar[str] = (
        "https://spclient.wg.spotify.com/playlist/v2/user/{}/rootlist/changes"
    )
    COLLECTION_URI: ClassVar[str] = (
        "https://spclient.wg.spotify.com/collection/v2/contains?market=from_token"
    )

    def __init__(self, session: AuthSession) -> None:
        self.session = session
        self.qc = QueryClient(session)

    async def _playlist_operation(self, *ops: dict[str, Any]) -> str:
        payload = {"ops": list(ops)}
        headers = {
            **self.session.authorized_headers,
            "accept": "application/json",
            "content-type": "application/json;charset=UTF-8",
        }
        response = await self.session.client.post(
            self.PLAYLIST_OP_URI, json=payload, headers=headers
        )

        if not response.json:
            raise PlaylistError("Playlist operation endpoint returned an empty response body")

        return response.json.uri

    async def _push_changes(self, *ops: dict[str, Any]) -> None:
        payload = {
            "deltas": [
                {
                    "ops": list(ops),
                    "info": {"source": {"client": "WEBPLAYER"}},
                }
            ]
        }
        attributes = await self.qc.get_profile_attributes()
        headers = {
            **self.session.authorized_headers,
            "accept": "application/json",
            "content-type": "application/json;charset=UTF-8",
        }
        response = await self.session.client.post(
            self.PLAYLIST_CHANGES_URI.format(attributes.username),
            json=payload,
            headers=headers,
        )

        if not response.json:
            raise PlaylistError("Playlist operation endpoint returned an empty response body")

        if not response.json.revision:
            raise PlaylistError("Playlist operation returned a non-valid revision")

    async def create_playlist(self, name: str, /) -> Playlist:
        create_op = {
            "kind": "UPDATE_LIST_ATTRIBUTES",
            "updateListAttributes": {"newAttributes": {"values": {"name": name}}},
        }
        playlist_id = await self._playlist_operation(create_op)

        add_op = {
            "kind": "ADD",
            "add": {
                "items": [
                    {
                        "uri": playlist_id,
                        "attributes": {"timestamp": str(int(time.time() * 1000))},
                    }
                ],
                "addFirst": True,
            },
        }
        await self._push_changes(add_op)
        return Playlist(self.session, playlist_id=playlist_id)

    async def create_folder(self, name: str) -> str:
        folder_hash = secrets.token_hex(8)
        timestamp = str(int(time.time() * 1000))

        start_item = {
            "uri": f"spotify:start-group:{folder_hash}:{quote(name)}",
            "attributes": {"timestamp": timestamp},
        }
        end_item = {
            "uri": f"spotify:end-group:{folder_hash}",
            "attributes": {"timestamp": timestamp},
        }

        add_op = {
            "kind": "ADD",
            "add": {
                "items": [start_item, end_item],
                "addFirst": True,
            },
        }

        await self._push_changes(add_op)
        return folder_hash

    async def move_items_to_folder(self, folder_hash: str, *item_uris: str) -> None:
        mov_op: dict[str, Any] = {
            "kind": "MOV",
            "mov": {
                "items": [{"uri": uri, "attributes": {}} for uri in item_uris],
                "addAfterItem": {
                    "uri": f"spotify:start-group:{folder_hash}",
                    "attributes": {},
                },
            },
        }
        await self._push_changes(mov_op)

    async def remove_items(self, *item_uris: str) -> None:
        rem_op = {
            "kind": "REM",
            "rem": {
                "items": [{"uri": uri} for uri in item_uris],
                "itemsAsKey": True,
            },
        }
        await self._push_changes(rem_op)


class Playlist:
    __slots__: tuple[str, ...] = (
        "session",
        "ph",
        "playlist_id",
    )

    def __init__(self, session: AuthSession, playlist_id: str) -> None:
        self.session = session
        self.ph = PlaylistHandler(session)
        self.playlist_id = (
            playlist_id
            if playlist_id.startswith("spotify:playlist:")
            else f"spotify:playlist:{playlist_id}"
        )

    async def add_tracks(
        self,
        *track_ids: str,
        move_type: Literal["TOP_OF_PLAYLIST", "BOTTOM_OF_PLAYLIST"] = "BOTTOM_OF_PLAYLIST",
    ) -> None:
        track_uris = [
            track_id if track_id.startswith("spotify:track:") else f"spotify:track:{track_id}"
            for track_id in track_ids
        ]
        response = await self.ph.qc.pathfinder_query(
            {
                "playlistItemUris": track_uris,
                "playlistUri": self.playlist_id,
                "newPosition": {"moveType": move_type, "fromUid": None},
            },
            "addToPlaylist",
        )

        if not response.addItemsToPlaylist:
            raise PlaylistError("Playlist operation returned an empty or invalid response body")

    async def fetch_content(self) -> AsyncGenerator[ObjectDict, None]:
        variables = {
            "uri": self.playlist_id,
            "offset": 0,
            "limit": 100,
            "includeEpisodeContentRatingsV2": True,
        }
        pages = self.ph.qc.paginate_query(variables, "fetchPlaylistContents")

        if not pages:
            raise PlaylistError("Playlist operation returned an empty or invalid response body")

        async for page in pages:
            for item in page.playlistV2.content._items:
                yield item

    async def remove_tracks(self, *track_ids: str) -> None:
        track_uris = {
            track_id if track_id.startswith("spotify:track:") else f"spotify:track:{track_id}"
            for track_id in track_ids
        }

        uids: list[str] = []
        async for item in self.fetch_content():
            if item.itemV2.data.uri in track_uris:
                uids.append(item.uid)
            if len(uids) == len(track_uris):
                break

        response = await self.ph.qc.pathfinder_query(
            {"uids": uids, "playlistUri": self.playlist_id},
            "removeFromPlaylist",
        )

        if not response.removeItemsFromPlaylist:
            raise PlaylistError("Playlist operation returned an empty or invalid response body")

    async def delete(self) -> None:
        await self.ph.remove_items(self.playlist_id)
