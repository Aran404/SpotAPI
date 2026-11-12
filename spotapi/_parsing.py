"""Coerce optional fields in Spotify response payloads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from .types import BaseClientError


def mapping(value: object) -> Mapping[str, Any]:
    """Return a mapping view, or an empty mapping for an absent nested object."""
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def records(value: object) -> tuple[Mapping[str, Any], ...]:
    """Return mapping-shaped entries from a sequence, or an empty tuple."""
    if not isinstance(value, (list, tuple)):
        return ()

    return tuple(mapping(item) for item in cast(list[object] | tuple[object, ...], value))


def integer(value: object, default: int = 0) -> int:
    """Parse a protocol integer without treating booleans as numeric values."""
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        return default

    try:
        return int(value)
    except ValueError:
        return default


def string_sequence(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(
        not isinstance(item, str) for item in cast(list[object] | tuple[object, ...], value)
    ):
        raise BaseClientError(f"Spotify returned an invalid {field_name} list")
    return tuple(cast(list[str] | tuple[str, ...], value))
