"""The same dated, grouped recents that Spotify shows in its web player."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Mapping
from contextlib import aclosing
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from .client import AsyncClient
from .datastruct import ObjectDict
from .playback import integer, mapping, records
from .query import QueryClient
from .session import AuthSession
from .types import BaseClientError


@dataclass(frozen=True, slots=True)
class RecentItem:
    uri: str
    name: str
    kind: str
    occurred_on: date | None
    activity: Literal["played", "saved"]
    contributors: tuple[str, ...] = ()
    image_url: str | None = None

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> RecentItem | None:
        """Parse one dated recent item; skip unavailable entities."""
        entity = mapping(mapping(row.get("entity")).get("data"))
        uri = entity.get("uri")

        if not isinstance(uri, str) or not uri.startswith("spotify:"):
            return None

        identity = mapping(entity.get("identityTrait"))
        contributors = records(mapping(identity.get("contributors")).get("items"))
        calendar = mapping(row.get("addedAt"))
        occurred_on = None

        if calendar:
            try:
                occurred_on = date(
                    integer(calendar.get("year")),
                    integer(calendar.get("month")),
                    integer(calendar.get("day")),
                )
            except ValueError as error:
                raise BaseClientError("Spotify returned an invalid history date") from error

        attributes = records(row.get("formatListAttributes"))
        saved = any(item.get("key") == "recent_type_saved" for item in attributes)
        cover = mapping(
            mapping(mapping(entity.get("visualIdentityTrait")).get("squareCoverImage")).get(
                "image"
            )
        )
        sources = records(mapping(cover.get("data")).get("sources"))
        image: Mapping[str, Any] = (
            min(sources, key=lambda source: abs(integer(source.get("width"), 300) - 300))
            if sources
            else {}
        )

        return cls(
            uri=uri,
            name=str(identity.get("name") or ""),
            kind=uri.split(":")[1],
            occurred_on=occurred_on,
            activity="saved" if saved else "played",
            contributors=tuple(str(item["name"]) for item in contributors if item.get("name")),
            image_url=image.get("url"),
        )


class ListeningHistory:
    """Fetch recents, including played contexts and explicitly marked saved items."""

    __slots__ = ("queries",)

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow an authenticated client for recent listening and saved activity."""
        session = client.session if isinstance(client, AsyncClient) else client
        self.queries = QueryClient(session)

    async def get(self, *, limit: int = 20, offset: int = 0) -> tuple[RecentItem, ...]:
        """Fetch one bounded page of Spotify's grouped recent activity."""
        self._validate(limit, offset)

        response = await self.queries.pathfinder_query(
            {"uris": ["spotify:list:recents:page"], "limit": limit, "offset": offset},
            "recents",
            max_attempts=1,
        )

        return self._items(self._page(response))

    async def pages(self, *, limit: int = 50) -> AsyncGenerator[tuple[RecentItem, ...], None]:
        """Stream recent-activity pages lazily without retaining earlier pages."""
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
