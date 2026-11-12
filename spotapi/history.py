"""The same dated, grouped recents that Spotify shows in its web player."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import aclosing

from ._parsing import mapping, records
from .client import AsyncClient
from .datastruct import ObjectDict
from .models.history import RecentItem
from .operations import Operations
from .query import QueryClient
from .session import AuthSession


class ListeningHistory:
    """Fetch recents, including played contexts and explicitly marked saved items."""

    __slots__ = ("queries",)

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow an authenticated client for recent listening and saved activity."""
        session = client.session if isinstance(client, AsyncClient) else client
        self.queries = QueryClient(session)

    async def get(self, *, limit: int = 20, offset: int = 0) -> tuple[RecentItem, ...]:
        """Read one page of grouped recent activity.

        Args:
            limit: Requested page size, from 1 to 100.
            offset: Nonnegative index of the first requested item.

        The returned dates describe recent contexts and saved actions. They are
        not exact per-track play timestamps or a complete listening ledger.
        """
        self._validate(limit, offset)

        response = await self.queries.pathfinder_query(
            {"uris": ["spotify:list:recents:page"], "limit": limit, "offset": offset},
            Operations.RECENTS,
        )

        return self._items(self._page(response))

    async def pages(self, *, limit: int = 50) -> AsyncGenerator[tuple[RecentItem, ...], None]:
        """Lazily read grouped recent activity in server order.

        Args:
            limit: Requested page size, from 1 to 100.

        Pages are fetched as iteration advances and earlier pages are not retained.
        The caller's authenticated client remains open after iteration ends.
        """
        self._validate(limit, 0)

        stream = self.queries.paginate_query(
            {"uris": ["spotify:list:recents:page"], "limit": limit, "offset": 0},
            "recents",
            extract_page=self._page,
        )

        async with aclosing(stream):
            async for page in stream:
                yield self._items(page)

    @staticmethod
    def _validate(limit: int, offset: int) -> None:
        """Reject invalid pagination limits and negative offsets."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative integer")

    @staticmethod
    def _page(response: ObjectDict) -> ObjectDict:
        """Extract the recents page or fail on an unexpected response shape."""
        lists = records(response.get("lists"))

        if not lists:
            return ObjectDict({"items": []})

        return ObjectDict(mapping(lists[0].get("items")))

    @staticmethod
    def _items(page: ObjectDict) -> tuple[RecentItem, ...]:
        """Parse available recent items while preserving Spotify's order."""
        items: list[RecentItem] = []

        for row in records(page.get("items")):
            item = RecentItem.from_dict(row)

            if item is not None:
                items.append(item)

        return tuple(items)
