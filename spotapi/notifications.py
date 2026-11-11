"""Read Spotify's notifications without changing their read state."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .client import AsyncClient
from .playback import mapping, records
from .session import AuthSession
from .types import BaseClientError


@dataclass(frozen=True, slots=True)
class Notification:
    id: str
    title: str
    created_at: datetime
    uri: str | None
    action: str | None
    image_url: str | None
    is_new: bool


@dataclass(frozen=True, slots=True)
class NotificationPage:
    items: tuple[Notification, ...]
    latest_cursor: str | None = field(repr=False)
    forward_cursor: str | None = field(repr=False)


class Notifications:
    """Use ``get()``; pass its forward_cursor to read the following page."""

    __slots__ = ("session",)

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow an authenticated client without acknowledging any notifications."""
        self.session = client.session if isinstance(client, AsyncClient) else client

    async def has_unread(self) -> bool:
        """Read the server's unread badge without resetting its cursor."""
        response = await self.session.client.get(
            "https://spclient.wg.spotify.com/gander/v2/GetUserHasUnreadNotification",
            headers=self.session.authorized_headers,
            query={"postFix": "a"},
            max_attempts=1,
        )
        value = mapping(response.json).get("userHasUnreadNotification")
        if type(value) is not bool:
            raise BaseClientError("Spotify returned no unread notification state")

        return value

    async def mark_seen(self, cursor: str) -> None:
        """Acknowledge the latest_cursor of a page explicitly opened by the user."""
        if not cursor.strip():
            raise ValueError("A notification cursor is required")

        await self.session.client.post(
            "https://spclient.wg.spotify.com/gander/v2/ResetLatestCursor",
            headers=self.session.authorized_headers,
            json={"cursor": cursor},
            max_attempts=1,
        )

    async def get(
        self, *, limit: int = 20, cursor: str | None = None, locale: str = "en"
    ) -> NotificationPage:
        """Fetch one notification page; pass forward_cursor to continue reading."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        query = {"limit": str(limit), "locale": locale}
        if cursor is not None:
            query["cursor"] = cursor

        response = await self.session.client.get(
            "https://spclient.wg.spotify.com/gander/v2/GetNotifications",
            headers=self.session.authorized_headers,
            query=query,
            max_attempts=1,
        )
        body = mapping(response.json)
        if not isinstance(body.get("notifications"), list):
            raise BaseClientError("Spotify returned no notification list")

        items: list[Notification] = []
        for row in records(body["notifications"]):
            action = mapping(row.get("action"))
            image = mapping(mapping(row.get("userAndEntityImage")).get("entityImage"))
            try:
                created = datetime.fromisoformat(row["createdTimestamp"])
            except (KeyError, TypeError, ValueError) as error:
                raise BaseClientError("Spotify returned an invalid notification date") from error
            items.append(
                Notification(
                    str(row["id"]),
                    str(row.get("title", "")),
                    created,
                    action.get("uri"),
                    action.get("type"),
                    image.get("imageUrl"),
                    row.get("isNew") is True,
                )
            )
        return NotificationPage(tuple(items), body.get("latestCursor"), body.get("forwardCursor"))
