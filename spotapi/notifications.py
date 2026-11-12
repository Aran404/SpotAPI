"""Read Spotify's notifications without changing their read state."""

from __future__ import annotations

from ._parsing import mapping
from ._protocol.routes import NOTIFICATIONS, NOTIFICATIONS_SEEN, NOTIFICATIONS_UNREAD
from .client import AsyncClient
from .models.notifications import NotificationPage
from .session import AuthSession
from .types import BaseClientError


class Notifications:
    """Read notifications and explicitly acknowledge viewed pages.

    The authenticated client remains owned by the caller. Reading a page or
    checking the unread badge does not mark notifications as seen.
    """

    __slots__ = (
        "http",
        "session",
    )

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow an authenticated client without acknowledging any notifications."""
        self.session = client.session if isinstance(client, AsyncClient) else client
        self.http = self.session.client

    async def has_unread(self) -> bool:
        """Read the server's unread badge without resetting its cursor."""
        response = await self.http.get(
            NOTIFICATIONS_UNREAD,
            authorized=True,
            query={"postFix": "a"},
        )
        value = mapping(response.json).get("userHasUnreadNotification")
        if type(value) is not bool:
            raise BaseClientError("Spotify returned no unread notification state")

        return value

    async def mark_seen(self, cursor: str) -> None:
        """Acknowledge a viewed page using its latest_cursor.

        Args:
            cursor: Nonempty acknowledgement cursor from a fetched page.

        This changes the unread state and is sent once. Fetching notifications
        alone never invokes this operation.
        """
        if not cursor.strip():
            raise ValueError("A notification cursor is required")

        await self.http.post(
            NOTIFICATIONS_SEEN,
            authorized=True,
            json={"cursor": cursor},
            max_attempts=1,
        )

    async def get(
        self, *, limit: int = 20, cursor: str | None = None, locale: str = "en"
    ) -> NotificationPage:
        """Read a notification page without acknowledging it.

        Args:
            limit: Requested page size, from 1 to 100.
            cursor: The previous page's forward_cursor; omit for the first page.
            locale: Spotify locale used for notification text.

        Returns:
            Typed notifications and continuation/acknowledgement cursors.

        Pass latest_cursor to mark_seen only when the page has been viewed.
        """
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        query = {"limit": str(limit), "locale": locale}
        if cursor is not None:
            query["cursor"] = cursor

        response = await self.http.get(
            NOTIFICATIONS,
            authorized=True,
            query=query,
        )
        return NotificationPage.from_dict(mapping(response.json))
