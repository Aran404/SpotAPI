"""Dated recent contexts and saved actions from the web player."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from spotapi._parsing import integer, mapping, records
from spotapi.types import BaseClientError


@dataclass(frozen=True, slots=True)
class RecentItem:
    """One dated recent context or saved action from Spotify's recents view.

    ``occurred_on`` is a calendar date when supplied. It is not an exact playback
    timestamp, and ``activity`` distinguishes played contexts from saved actions.
    """

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
