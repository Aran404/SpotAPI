"""Authenticated access to Spotify's liked tracks."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from contextlib import aclosing
from typing import Any
from uuid import uuid4

from .catalogue import parse_spotify_resource
from .client import AsyncClient
from .datastruct import ObjectDict
from .library_models import LibraryItem, LibraryPage, SavedTrack
from .playback import mapping, records
from .query import QueryClient
from .session import AuthSession
from .types import BaseClientError


def _page_options(limit: int, offset: int) -> None:
    """Validate the library's bounded limit and nonnegative offset."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be between 1 and 100")
    if type(offset) is not int or offset < 0:
        raise ValueError("offset must be a non-negative integer")


class _LibraryActions:

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow the caller's session for library reads and explicit mutations."""
        session = client.session if isinstance(client, AsyncClient) else client
        self.queries = QueryClient(session)

    async def contains(self, tracks: Sequence[str]) -> tuple[bool, ...]:
        """Return saved flags in input order, batching at most 50 resources per request."""
        uris = self._uris(tracks)
        flags: list[bool] = []

        for offset in range(0, len(uris), 50):
            batch = uris[offset : offset + 50]
            response = await self.queries.pathfinder_query(
                {"uris": batch},
                "areEntitiesInLibrary",
                max_attempts=1,
            )

            found = records(response.get("lookup"))

            if len(found) != len(batch):
                raise BaseClientError("Spotify returned an incomplete library lookup")

            for item in found:
                saved = mapping(item.get("data")).get("saved")

                if not isinstance(saved, bool):
                    raise BaseClientError("Spotify returned an invalid saved-track flag")

                flags.append(saved)

        return tuple(flags)

    async def add(self, tracks: Sequence[str]) -> None:
        """Save supplied resources to the library; mutations are never replayed."""
        await self._change("addToLibrary", tracks)

    async def remove(self, tracks: Sequence[str]) -> None:
        """Unsave supplied resources; mutations are never replayed."""
        await self._change("removeFromLibrary", tracks)

    async def _change(self, operation: str, tracks: Sequence[str]) -> None:
        """Normalize resources and send library mutations in bounded batches."""
        uris = self._uris(tracks)

        for offset in range(0, len(uris), 50):
            variables: dict[str, Any] = {"libraryItemUris": uris[offset : offset + 50]}

            if operation == "addToLibrary":
                variables["interactionId"] = str(uuid4())

            response = await self.queries.pathfinder_query(variables, operation, max_attempts=1)
            key, typename = (
                ("addLibraryItems", "AddLibraryItemsResponse")
                if operation == "addToLibrary"
                else ("removeLibraryItems", "RemoveLibraryItemsResponse")
            )
            result = mapping(response.get(key))
            if result.get("__typename") != typename:
                raise BaseClientError(
                    "Spotify did not confirm the library change; reconcile saved state before retrying"
                )

    @staticmethod
    def _uris(values: Sequence[str]) -> list[str]:
        """Normalize resource identifiers and reject a string used as a collection."""
        if isinstance(values, str):
            raise TypeError("Pass a collection of Spotify resources")
        uris: list[str] = []
        for value in values:
            resource = parse_spotify_resource(
                value, "track" if ":" not in value and "/" not in value else None
            )
            if resource.kind not in {
                "track",
                "album",
                "artist",
                "show",
                "episode",
                "audiobook",
                "playlist",
            }:
                raise ValueError("This resource cannot be saved to the library")
            uris.append(resource.uri)
        return uris


class LikedTracks(_LibraryActions):
    """Check, save and paginate liked tracks using one borrowed client."""

    @staticmethod
    def _uris(values: Sequence[str]) -> list[str]:
        """Normalize resource identifiers and reject a string used as a collection."""
        if isinstance(values, str):
            raise TypeError("Pass a collection of tracks")
        return [parse_spotify_resource(value, "track").uri for value in values]

    @staticmethod
    def _page(response: ObjectDict) -> ObjectDict:
        """Extract the expected library page and reject missing item lists."""
        page = mapping(mapping(mapping(response.get("me")).get("library")).get("tracks"))
        if not isinstance(page.get("items"), list):
            raise BaseClientError("Spotify returned no saved tracks")
        return ObjectDict(page)

    async def get(self, *, limit: int = 50, offset: int = 0) -> tuple[SavedTrack, ...]:
        """Fetch a bounded page of saved items without changing the library."""
        _page_options(limit, offset)
        response = await self.queries.pathfinder_query(
            {"limit": limit, "offset": offset}, "fetchLibraryTracks", max_attempts=1
        )
        return tuple(SavedTrack.from_dict(row) for row in records(self._page(response)["items"]))

    async def pages(self, *, limit: int = 100) -> AsyncGenerator[tuple[SavedTrack, ...], None]:
        """Stream library pages lazily using Spotify's returned totals."""
        _page_options(limit, 0)
        pages = self.queries.paginate_query(
            {"limit": limit, "offset": 0}, "fetchLibraryTracks", extract_page=self._page
        )
        async with aclosing(pages):
            async for page in pages:
                yield tuple(SavedTrack.from_dict(row) for row in records(page["items"]))


class Library(_LibraryActions):
    """Browse saved items with ``get()`` or stream them with ``items()``."""

    @staticmethod
    def _page(response: ObjectDict) -> ObjectDict:
        """Extract the expected library page and reject missing item lists."""
        page = mapping(mapping(response.get("me")).get("libraryV3"))
        if not isinstance(page.get("items"), list):
            raise BaseClientError("Spotify rejected the library query or its filters")
        return ObjectDict(page)

    @staticmethod
    def _variables(
        limit: int,
        offset: int,
        filters: Sequence[str],
        order: str | None,
        query: str,
        folder: str | None,
    ) -> dict[str, Any]:
        """Build native library filters, ordering and pagination variables."""
        _page_options(limit, offset)
        if isinstance(filters, str):
            raise TypeError("Pass a collection of library filter IDs")
        return {
            "limit": limit,
            "offset": offset,
            "filters": list(filters),
            "order": order,
            "textFilter": query,
            "features": [],
            "folderUri": folder,
            "flatten": False,
            "expandedFolders": [],
            "includeFoldersWhenFlattening": True,
        }

    async def get(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        filters: Sequence[str] = (),
        order: str | None = None,
        query: str = "",
        folder: str | None = None,
    ) -> LibraryPage:
        """Fetch a bounded page of saved items without changing the library."""
        variables = self._variables(limit, offset, filters, order, query, folder)
        response = await self.queries.pathfinder_query(variables, "libraryV3", max_attempts=1)
        return LibraryPage.from_dict(self._page(response))

    async def pages(
        self,
        *,
        limit: int = 100,
        filters: Sequence[str] = (),
        order: str | None = None,
        query: str = "",
        folder: str | None = None,
    ) -> AsyncGenerator[LibraryPage, None]:
        """Stream library pages lazily using Spotify's returned totals."""
        variables = self._variables(limit, 0, filters, order, query, folder)
        pages = self.queries.paginate_query(variables, "libraryV3", extract_page=self._page)
        async with aclosing(pages):
            async for page in pages:
                yield LibraryPage.from_dict(page)

    async def items(self, *, limit: int = 100) -> AsyncGenerator[LibraryItem, None]:
        """Yield saved library items individually while releasing page resources."""
        async with aclosing(self.pages(limit=limit)) as pages:
            async for page in pages:
                for item in page.items:
                    yield item

    async def pin(self, value: str) -> None:
        """Pin a supported resource in the user's library."""
        await self._pin("pinLibraryItem", value)

    async def unpin(self, value: str) -> None:
        """Unpin a library resource without removing it."""
        await self._pin("unpinLibraryItem", value)

    async def _pin(self, operation: str, value: str) -> None:
        """Send one native pin or unpin mutation for a normalized resource."""
        resource = parse_spotify_resource(
            value, "playlist" if ":" not in value and "/" not in value else None
        )
        response = await self.queries.pathfinder_query(
            {"pinnableItemUri": resource.uri}, operation, max_attempts=1
        )
        key = "pinItemInLibrary" if operation == "pinLibraryItem" else "unpinItemInLibrary"
        if mapping(response.get(key)).get("pinResult") != "SUCCESSFUL":
            raise BaseClientError(
                "Spotify did not confirm the pin change; reconcile library state before retrying"
            )
