"""Authenticated Spotify account profile model."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from spotapi._decoding import from_dict
from spotapi.types import BaseClientError

__all__ = ("Profile",)


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
        """Validate required profile identity and optional native response fields."""
        try:
            return from_dict(cls, data)
        except (TypeError, ValueError) as error:
            raise BaseClientError(
                f"Spotify returned invalid profile attributes: {error}"
            ) from error
