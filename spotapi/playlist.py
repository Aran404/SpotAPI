"""Async operations for Spotify playlists and library folders.

``PlaylistHandler`` manages playlist creation and library-rootlist changes.
``Playlist`` exposes track operations for an existing playlist.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import AsyncGenerator, Iterable
from contextlib import aclosing
from typing import Final, Literal, TypeAlias, cast
from urllib.parse import quote

from .catalogue import Catalogue
from .client import AsyncClient
from .datastruct import ObjectDict
from .discovery import RecommendedTrack
from .public import Public
from .query import QueryClient
from .session import AuthSession
from .specialized.data_wrappers import PlaylistDetails, PlaylistEntry, from_dict
from .types import PlaylistError

__all__: tuple[str, ...] = (
    "MoveType",
    "Playlist",
    "PlaylistHandler",
)

MoveType: TypeAlias = Literal["TOP_OF_PLAYLIST", "BOTTOM_OF_PLAYLIST"]
_JsonValue: TypeAlias = (
    str | int | float | bool | None | list["_JsonValue"] | dict[str, "_JsonValue"]
)
_Op: TypeAlias = dict[str, _JsonValue]

_PLAYLIST_URL: Final[str] = "https://spclient.wg.spotify.com/playlist/v2/playlist"
_COVER_UPLOAD_URL: Final[str] = "https://image-upload.spotify.com/v4/playlist"
_ROOTLIST_URL: Final[str] = "https://spclient.wg.spotify.com/playlist/v2/user/{}/rootlist/changes"
_PAGE_LIMIT: Final[int] = 100

_JSON_HEADERS: Final[dict[str, str]] = {
    "accept": "application/json",
    "content-type": "application/json;charset=UTF-8",
}

_EMPTY_BODY: Final[str] = "Playlist operation endpoint returned an empty response body"
_BAD_RESPONSE: Final[str] = "Playlist operation returned an empty or invalid response body"
_BAD_REVISION: Final[str] = "Playlist operation returned a non-valid revision"


def _now_ms() -> str:
    """Return an integer millisecond timestamp in Spotify's string representation."""
    return str(time.time_ns() // 1_000_000)


def _as_uri(kind: Literal["track", "playlist"], value: str) -> str:
    """Normalize the same URLs, URIs and IDs accepted by catalogue lookups."""
    return Public.parse_url(value, kind=kind).uri


def _item(uri: str) -> _Op:
    """Build a rootlist item reference from an already normalized URI."""
    return {"uri": uri, "attributes": {}}


def _stamped(uri: str, timestamp: str) -> _Op:
    """Build a rootlist item with its insertion timestamp."""
    return {"uri": uri, "attributes": {"timestamp": timestamp}}


def _set_name_op(name: str) -> _Op:
    """Build the list-attribute operation used to name a new playlist."""
    return {
        "kind": "UPDATE_LIST_ATTRIBUTES",
        "updateListAttributes": {"newAttributes": {"values": {"name": name}}},
    }


def _add_to_top_op(*items: _Op) -> _Op:
    """Build an insertion at the beginning of the rootlist."""
    return {
        "kind": "ADD",
        "add": {"items": list(items), "addFirst": True},
    }


def _move_op(uris: Iterable[str], *, after: str) -> _Op:
    """Build a rootlist move relative to a known anchor."""
    return {
        "kind": "MOV",
        "mov": {
            "items": [_item(uri) for uri in uris],
            "addAfterItem": _item(after),
        },
    }


def _remove_op(uris: Iterable[str]) -> _Op:
    """Build removal by URI rather than by a stale rootlist index."""
    return {
        "kind": "REM",
        "rem": {
            "items": [{"uri": uri} for uri in uris],
            "itemsAsKey": True,
        },
    }


class PlaylistHandler:
    """Manage playlist creation and changes to a user's library rootlist.

    Attributes:
        session: Authorized session used for playlist mutations.
        qc: Query client sharing the session.
    """

    __slots__ = ("session", "qc", "_username")

    def __init__(self, session: AuthSession | AsyncClient) -> None:
        """Initialize the handler with an authorized Spotify session.

        Args:
            session: Session used to authenticate playlist operations.
        """
        self.session = session.session if isinstance(session, AsyncClient) else session
        self.qc = QueryClient(self.session)
        self._username: str | None = None

    def _headers(self) -> dict[str, str]:
        """Combine managed authorization with JSON request headers."""
        return {**self.session.authorized_headers, **_JSON_HEADERS}

    async def _post(self, url: str, payload: _Op) -> ObjectDict:
        """Send a mutation and require a nonempty JSON response."""
        response = await self.session.client.post(
            url, max_attempts=1, json=payload, headers=self._headers()
        )

        body = response.json

        if not body:
            raise PlaylistError(_EMPTY_BODY)

        return body

    async def _get_username(self) -> str:
        # The username cannot change during a session, so fetch it once.
        """Cache the immutable username for this handler's authenticated session."""
        if self._username is None:
            attributes = await self.qc.get_profile_attributes()

            username: str = attributes.username
            self._username = username

        return self._username

    async def _playlist_operation(self, *ops: _Op) -> str:
        """Create a playlist from native operations and require its returned URI."""
        body = await self._post(_PLAYLIST_URL, {"ops": list(ops)})

        uri: object = body.get("uri")

        if not isinstance(uri, str) or not uri:
            raise PlaylistError("Playlist creation returned no playlist URI")

        return uri

    async def _push_changes(self, *ops: _Op) -> None:
        """Apply rootlist changes once and require a resulting revision."""
        payload: _Op = {
            "deltas": [
                {
                    "ops": list(ops),
                    "info": {"source": {"client": "WEBPLAYER"}},
                }
            ]
        }
        url = _ROOTLIST_URL.format(quote(await self._get_username(), safe=""))

        body = await self._post(url, payload)

        if not body.get("revision"):
            raise PlaylistError(_BAD_REVISION)

    async def create_playlist(self, name: str, /) -> Playlist:
        """Create a playlist and add it to the user's library.

        Args:
            name: Display name of the new playlist.

        Returns:
            A playlist instance that reuses this handler.

        Raises:
            PlaylistError: If a mutation returns an empty response or
                an invalid rootlist revision.
        """
        uri = await self._playlist_operation(_set_name_op(name))

        await self._push_changes(_add_to_top_op(_stamped(uri, _now_ms())))

        return Playlist(self.session, uri, handler=self)

    async def create_folder(self, name: str) -> str:
        """Create a folder at the top of the user's library.

        Args:
            name: Display name of the new folder.

        Returns:
            The folder identifier, for use with ``move_items_to_folder``.

        Raises:
            PlaylistError: If the rootlist response is empty or has
                an invalid revision.
        """
        folder_hash = secrets.token_hex(8)
        title = quote(name, safe="")
        now = _now_ms()

        await self._push_changes(
            _add_to_top_op(
                _stamped(f"spotify:start-group:{folder_hash}:{title}", now),
                _stamped(f"spotify:end-group:{folder_hash}", now),
            )
        )

        return folder_hash

    async def move_items_to_folder(self, folder_hash: str, *item_uris: str) -> None:
        """Move library items into an existing folder.

        Args:
            folder_hash: Identifier returned by ``create_folder``.
            *item_uris: Spotify URIs of the items to move.

        Notes:
            Passing no items has no effect.

        Raises:
            PlaylistError: If the rootlist response is missing or invalid.
        """
        if not item_uris:
            return

        anchor = f"spotify:start-group:{folder_hash}"

        await self._push_changes(_move_op(item_uris, after=anchor))

    async def remove_items(self, *item_uris: str) -> None:
        """Remove items from the user's library rootlist.

        Args:
            *item_uris: Spotify URIs of the items to remove.

        Notes:
            Passing no items has no effect.

        Raises:
            PlaylistError: If the rootlist response is missing or invalid.
        """
        if not item_uris:
            return

        await self._push_changes(_remove_op(item_uris))

    async def edit_playlist(
        self, playlist: str, *, name: str | None = None, description: str | None = None
    ) -> None:
        """Update supplied metadata; an empty description clears it, and None leaves it alone."""
        if name is not None and not name.strip():
            raise ValueError("A playlist name cannot be empty")
        if name is None and description is None:
            return

        values: _Op = {"formatAttributes": [], "pictureSize": []}
        cleared: list[_JsonValue] = []
        if name is not None:
            values["name"] = name
        if description is not None:
            if description:
                values["description"] = description
            else:
                cleared.append("LIST_DESCRIPTION")

        await self._set_playlist_attributes(playlist, values, cleared)

    async def _set_playlist_attributes(
        self, playlist: str, values: _Op, cleared: list[_JsonValue]
    ) -> None:
        """Apply a metadata change and require Spotify's resulting revision."""
        operation: _Op = {
            "kind": "UPDATE_LIST_ATTRIBUTES",
            "updateListAttributes": {"newAttributes": {"values": values, "noValue": cleared}},
        }
        body = await self._post(
            _PLAYLIST_URL
            + "/"
            + quote(_as_uri("playlist", playlist).rsplit(":", 1)[-1], safe="")
            + "/changes",
            {
                "deltas": [{"ops": [operation], "info": {"source": {"client": "WEBPLAYER"}}}],
                "wantSyncResult": True,
            },
        )
        if not body.get("revision"):
            raise PlaylistError(_BAD_REVISION)

    async def set_playlist_cover(self, playlist: str, jpeg: bytes | None) -> None:
        """Upload a JPEG cover or clear it with None."""
        uri = _as_uri("playlist", playlist)
        values: _Op = {"formatAttributes": [], "pictureSize": []}
        if jpeg is None:
            await self._set_playlist_attributes(uri, values, ["LIST_PICTURE"])
            return

        if not jpeg.startswith(b"\xff\xd8\xff"):
            raise ValueError("Provide JPEG image bytes or None")

        upload = await self.session.client.post(
            _COVER_UPLOAD_URL,
            body=jpeg,
            headers={**self.session.authorized_headers, "content-type": "image/jpeg"},
            max_attempts=1,
        )
        token: object = upload.json.get("uploadToken") if upload.json is not None else None
        if not isinstance(token, str) or not token:
            raise PlaylistError("Spotify returned no playlist cover upload token")

        playlist_id = quote(uri.rsplit(":", 1)[-1], safe="")
        registered = await self._post(
            f"{_PLAYLIST_URL}/{playlist_id}/register-image", {"uploadToken": token}
        )
        picture: object = registered.get("picture")
        if not isinstance(picture, str) or not picture:
            raise PlaylistError("Spotify returned no registered playlist picture")

        values["picture"] = picture
        await self._set_playlist_attributes(uri, values, [])

    async def get_playlist_metadata(self, playlist: str) -> PlaylistDetails:
        """Read canonical metadata directly; omit GraphQL-only presentation fields."""
        uri = _as_uri("playlist", playlist)
        response = await self.session.client.get(
            _PLAYLIST_URL + "/" + quote(uri.rsplit(":", 1)[-1], safe=""),
            headers=self._headers(),
            max_attempts=1,
        )
        body = response.json
        attributes = body.get("attributes") if body is not None else None
        if (
            body is None
            or not isinstance(attributes, ObjectDict)
            or not isinstance(attributes.get("name"), str)
        ):
            raise PlaylistError("Spotify returned no playlist metadata")

        return from_dict(
            PlaylistDetails,
            {
                "uri": uri,
                "name": attributes["name"],
                "description": attributes.get("description", ""),
                "revisionId": body.get("revision"),
                "content": {"totalCount": body.get("length")},
                "ownerV2": {"data": {"username": body.get("ownerUsername")}},
            },
        )

    async def set_playlist_published(self, playlist: str, published: bool) -> None:
        """Show or hide this playlist on your profile; this does not change access permissions."""
        if type(published) is not bool:
            raise TypeError("published must be a boolean")
        await self._push_changes(
            {
                "kind": "UPDATE_ITEM_ATTRIBUTES",
                "updateItemAttributes": {
                    "item": {"uri": _as_uri("playlist", playlist)},
                    "newAttributes": {
                        "values": {
                            "public": published,
                            "formatAttributes": [],
                            "availableSignals": [],
                        },
                        "noValue": [],
                    },
                },
            }
        )


class Playlist:
    """Read and modify a Spotify playlist using an authorized session.

    Attributes:
        session: Authorized session used for playlist operations.
        ph: Handler used for mutations and content queries.
        playlist_id: Full Spotify playlist URI.
    """

    __slots__ = ("session", "ph", "playlist_id")

    def __init__(
        self,
        session: AuthSession | AsyncClient,
        playlist_id: str,
        *,
        handler: PlaylistHandler | None = None,
    ) -> None:
        """Initialize a playlist reference without making a request.

        Args:
            session: Authorized session used for playlist operations.
            playlist_id: Spotify playlist ID or full playlist URI.
            handler: Optional handler to share query and session state.
        """
        self.session = session.session if isinstance(session, AsyncClient) else session
        self.ph = handler if handler is not None else PlaylistHandler(self.session)
        self.playlist_id = _as_uri("playlist", playlist_id)

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<{type(self).__name__} playlist_id={self.playlist_id!r}>"

    def __eq__(self, other: object) -> bool:
        """Compare playlist identity by normalized Spotify URI."""
        if not isinstance(other, Playlist):
            return NotImplemented

        return self.playlist_id == other.playlist_id

    def __hash__(self) -> int:
        """Hash the normalized Spotify playlist URI."""
        return hash(self.playlist_id)

    async def add_tracks(
        self,
        *track_ids: str,
        move_type: MoveType = "BOTTOM_OF_PLAYLIST",
    ) -> None:
        """Add tracks to the top or bottom of the playlist.

        Args:
            *track_ids: Spotify track IDs or full track URIs to add.
            move_type: Where to insert tracks. Defaults to the bottom.

        Raises:
            PlaylistError: If the query returns no addition result.

        Notes:
            Passing no tracks has no effect.
        """
        if not track_ids:
            return

        response = await self.ph.qc.pathfinder_query(
            {
                "playlistItemUris": [_as_uri("track", track_id) for track_id in track_ids],
                "playlistUri": self.playlist_id,
                "newPosition": {"moveType": move_type, "fromUid": None},
            },
            "addToPlaylist",
            max_attempts=1,
        )

        result = response.get("addItemsToPlaylist")
        if not isinstance(result, ObjectDict):
            raise PlaylistError(_BAD_RESPONSE)
        if result.get("__typename") != "AddItemsToPlaylistPayload":
            raise PlaylistError(
                f"Spotify rejected playlist addition: {result.get('__typename')!r}"
            )

    async def fetch_content(self) -> AsyncGenerator[ObjectDict, None]:
        """Yield playlist items across all paginated content responses.

        Yields:
            Each playlist item, including its occurrence-specific UID.
        """
        variables = {
            "uri": self.playlist_id,
            "offset": 0,
            "limit": _PAGE_LIMIT,
            "includeEpisodeContentRatingsV2": True,
        }
        pages = self.ph.qc.paginate_query(
            variables,
            "fetchPlaylistContents",
            extract_page=lambda response: response.playlistV2.content,
        )

        async for page in pages:
            items: object = page.get("items", page.get("_items"))

            if not isinstance(items, list):
                raise PlaylistError("Playlist content response has no items list")

            for item in cast(list[object], items):
                if not isinstance(item, ObjectDict):
                    raise PlaylistError("Playlist content contains an invalid item")

                yield item

    async def get(self, *, fresh: bool = True) -> PlaylistDetails:
        """Read canonical metadata, avoiding GraphQL's delayed metadata cache.

        Use fresh=False for GraphQL artwork and presentation fields, which can lag behind edits.
        """
        if fresh:
            return await self.ph.get_playlist_metadata(self.playlist_id)
        async with Catalogue(self.session) as catalogue:
            return await catalogue.get_playlist(self.playlist_id)

    async def edit(self, *, name: str | None = None, description: str | None = None) -> None:
        """Change supplied metadata; an empty description clears it, and None leaves it alone."""
        await self.ph.edit_playlist(self.playlist_id, name=name, description=description)

    async def set_cover(self, jpeg: bytes | None) -> None:
        """Set a custom JPEG cover, or pass None to restore the default artwork."""
        await self.ph.set_playlist_cover(self.playlist_id, jpeg)

    async def set_published(self, published: bool) -> None:
        """Show or hide this playlist on your profile without changing access permissions."""
        await self.ph.set_playlist_published(self.playlist_id, published)

    async def recommendations(self, *, limit: int = 20) -> tuple[RecommendedTrack, ...]:
        """Read suggested tracks for this playlist without adding any of them."""
        async with Catalogue(self.session) as catalogue:
            return await catalogue.get_playlist_recommendations(self.playlist_id, limit=limit)

    async def items(self, *, limit: int = 100) -> AsyncGenerator[PlaylistEntry, None]:
        """Stream typed occurrences with this playlist's authentication, including private items."""
        async with Catalogue(self.session) as catalogue:
            pages = catalogue.get_playlist_items(self.playlist_id, limit=limit)
            async with aclosing(pages):
                async for page in pages:
                    for item in page:
                        yield item

    async def _resolve_uids(self, uris: set[str]) -> list[str]:
        """Find the first occurrence UID for each requested track URI."""
        pending = uris.copy()
        uids: list[str] = []

        async with aclosing(self.fetch_content()) as content:
            async for item in content:
                entity: object = item.get("itemV2")
                data: object = entity.get("data") if isinstance(entity, ObjectDict) else None

                if not isinstance(data, ObjectDict):
                    continue

                uri: object = data.get("uri")

                if not isinstance(uri, str):
                    continue

                if uri not in pending:
                    continue

                uid: object = item.get("uid")

                if not isinstance(uid, str) or not uid:
                    raise PlaylistError("Matching playlist item has no occurrence UID")

                pending.discard(uri)
                uids.append(uid)

                if not pending:
                    break

        return uids

    async def remove_tracks(self, *track_ids: str) -> None:
        """Remove the first occurrence of each requested track.

        Args:
            *track_ids: Spotify track IDs or full track URIs to remove.

        Raises:
            PlaylistError: If the removal query returns no result.

        Notes:
            Repeated IDs are deduplicated. Missing tracks and an empty
            argument list result in no changes to the playlist.
        """
        track_uris = {_as_uri("track", track_id) for track_id in track_ids}

        if not track_uris:
            return

        uids = await self._resolve_uids(track_uris)

        await self.remove_occurrences(*uids)

    async def remove_occurrences(self, *entries: PlaylistEntry | str) -> None:
        """Remove exact occurrence UIDs without searching or deleting other duplicates."""
        uids = list(
            dict.fromkeys(
                entry.uid if isinstance(entry, PlaylistEntry) else entry for entry in entries
            )
        )
        if any(not uid for uid in uids):
            raise ValueError("Each playlist occurrence must have a UID")

        if not uids:
            return

        response = await self.ph.qc.pathfinder_query(
            {"uids": uids, "playlistUri": self.playlist_id},
            "removeFromPlaylist",
            max_attempts=1,
        )

        result = response.get("removeItemsFromPlaylist")
        if not isinstance(result, ObjectDict):
            raise PlaylistError(_BAD_RESPONSE)
        if result.get("__typename") != "RemoveItemsFromPlaylistPayload":
            raise PlaylistError(f"Spotify rejected playlist removal: {result.get('__typename')!r}")

    async def move_occurrences(
        self,
        *entries: PlaylistEntry | str,
        before: PlaylistEntry | str | None = None,
        after: PlaylistEntry | str | None = None,
    ) -> None:
        """Move exact occurrences before or after an anchor, or to the end."""
        if before is not None and after is not None:
            raise ValueError("Specify either before or after")

        uids = list(
            dict.fromkeys(
                entry.uid if isinstance(entry, PlaylistEntry) else entry for entry in entries
            )
        )
        anchor = before if before is not None else after
        anchor_uid = anchor.uid if isinstance(anchor, PlaylistEntry) else anchor
        if any(not uid for uid in uids) or (anchor is not None and not anchor_uid):
            raise ValueError("Each playlist occurrence must have a UID")

        if anchor_uid in uids:
            raise ValueError("The anchor cannot be one of the moved occurrences")

        if not uids:
            return

        move_type = (
            "BEFORE_UID"
            if before is not None
            else "AFTER_UID" if after is not None else "BOTTOM_OF_PLAYLIST"
        )
        response = await self.ph.qc.pathfinder_query(
            {
                "uids": uids,
                "playlistUri": self.playlist_id,
                "newPosition": {"moveType": move_type, "fromUid": anchor_uid},
            },
            "moveItemsInPlaylist",
            max_attempts=1,
        )

        result = response.get("moveItemsInPlaylist")
        if not isinstance(result, ObjectDict):
            raise PlaylistError(_BAD_RESPONSE)
        if result.get("__typename") != "MoveItemsInPlaylistPayload":
            raise PlaylistError(f"Spotify rejected playlist move: {result.get('__typename')!r}")

    async def delete(self) -> None:
        """Remove this playlist from the user's library rootlist.

        Raises:
            PlaylistError: If the rootlist response is missing or invalid.
        """
        await self.ph.remove_items(self.playlist_id)
