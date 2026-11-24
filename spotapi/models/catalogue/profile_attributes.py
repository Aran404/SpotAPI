"""Authenticated Spotify account profile model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from spotapi._decoding import from_dict
from spotapi.types import BaseClientError

__all__ = ("Profile",)


def _avatar_url(value: object) -> object:
    """Return the largest image URL from an avatar object; pass other values through."""
    if not isinstance(value, Mapping):
        return value
    sources: object = cast(Mapping[str, object], value).get("sources")
    if not isinstance(sources, list):
        return None
    best: str | None = None
    best_area = -1
    for source in cast(list[object], sources):
        if not isinstance(source, Mapping):
            continue
        entry = cast(Mapping[str, object], source)
        url, width, height = entry.get("url"), entry.get("width"), entry.get("height")
        if not isinstance(url, str) or not url:
            continue
        area = width * height if isinstance(width, int) and isinstance(height, int) else 0
        if area > best_area:
            best, best_area = url, area
    return best


@dataclass(slots=True)
class Profile:
    """Authenticated profile attributes with Python field names."""

    account_id: str
    name: str
    uri: str
    username: str
    avatar: str | None = None
    avatar_background_color: int | None = None
    social_handle: str | None = None

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Profile:
        """Validate required profile identity and optional native response fields.

        Spotify sends ``avatar`` either as a URL string or as an image object
        (``{"sources": [{"url", "width", "height"}, ...]}``). The object form is
        reduced to the URL of its largest source so ``avatar`` stays a string.
        """
        if "avatar" in data:
            data = {**data, "avatar": _avatar_url(data["avatar"])}
        try:
            return from_dict(cls, data)
        except (TypeError, ValueError) as error:
            raise BaseClientError(
                f"Spotify returned invalid profile attributes: {error}"
            ) from error
