"""Notification identities, timestamps and page cursors."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from spotapi._decoding import from_dict
from spotapi._parsing import mapping, records
from spotapi.types import BaseClientError


@dataclass(frozen=True, slots=True)
class Notification:
    """One notification, with the timestamp and optional action supplied by Spotify."""

    id: str
    title: str
    created_at: datetime
    uri: str | None
    action: str | None
    image_url: str | None
    is_new: bool

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> Notification:
        """Decode a notification or raise a contextual response-contract error."""
        action = mapping(row.get("action"))
        image = mapping(mapping(row.get("userAndEntityImage")).get("entityImage"))
        try:
            created = datetime.fromisoformat(row["createdTimestamp"])
            item = from_dict(
                cls,
                {
                    "id": row.get("id"),
                    "title": row.get("title", ""),
                    "created_at": created,
                    "uri": action.get("uri"),
                    "action": action.get("type"),
                    "image_url": image.get("imageUrl"),
                    "is_new": row.get("isNew") is True,
                },
            )
        except (KeyError, TypeError, ValueError) as error:
            raise BaseClientError(f"Spotify returned an invalid notification: {error}") from error

        if not item.id:
            raise BaseClientError("Spotify returned a notification without an ID")
        return item


@dataclass(frozen=True, slots=True)
class NotificationPage:
    """A page whose cursors support explicit acknowledgement and subsequent reads."""

    items: tuple[Notification, ...]
    latest_cursor: str | None = field(repr=False)
    forward_cursor: str | None = field(repr=False)

    @classmethod
    def from_dict(cls, body: Mapping[str, Any]) -> NotificationPage:
        """Read notification records and validate the optional opaque cursors."""
        if not isinstance(body.get("notifications"), list):
            raise BaseClientError("Spotify returned no notification list")

        latest = body.get("latestCursor")
        forward = body.get("forwardCursor")
        if any(value is not None and not isinstance(value, str) for value in (latest, forward)):
            raise BaseClientError("Spotify returned an invalid notification cursor")

        return cls(
            tuple(Notification.from_dict(row) for row in records(body["notifications"])),
            latest,
            forward,
        )
