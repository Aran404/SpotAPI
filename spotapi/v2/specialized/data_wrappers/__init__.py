from __future__ import annotations

import types
from dataclasses import MISSING, fields, is_dataclass
from functools import lru_cache
from typing import Any, TypeVar, Union, get_args, get_origin, TypeGuard, get_type_hints

from spotapi.v2.specialized.data_wrappers.common import (
    Sources,
    ColorDark,
    ExtractedColors,
    ExtractedColorSet,
    SquareCoverImage,
    VisualIdentity,
)
from spotapi.v2.specialized.data_wrappers.playlist import Playlist
from spotapi.v2.specialized.data_wrappers.track import Track
from spotapi.v2.specialized.data_wrappers.artist import Artist
from spotapi.v2.specialized.data_wrappers.podcast import Podcast
from spotapi.v2.specialized.data_wrappers.album import Album

__all__: tuple[str, ...] = (
    # entity types
    "Track",
    "Playlist",
    "Artist",
    "Podcast",
    "Album",
    # shared visual types
    "Sources",
    "ColorDark",
    "ExtractedColors",
    "VisualIdentity",
    "SquareCoverImage",
    "ExtractedColorSet",
    # deserializer
    "from_dict",
)

T = TypeVar("T")

_NoneType = type(None)

_UNION_ORIGINS: tuple[Any, ...] = (
    Union,
    *((types.UnionType,) if hasattr(types, "UnionType") else ()),
)
_SEQUENCE_TYPES: tuple[type, ...] = (
    list,
    tuple,
    set,
    frozenset,
)


def _is_dataclass_type(obj: Any) -> TypeGuard[type[Any]]:
    return isinstance(obj, type) and is_dataclass(obj)


def _to_camel_case(name: str) -> str:
    first, *rest = name.split("_")
    return first + "".join(part.capitalize() for part in rest)


def _extract_value(data: dict[str, Any], field_name: str) -> tuple[bool, Any]:
    if field_name in data:
        return True, data[field_name]

    camel_name = _to_camel_case(field_name)
    if camel_name in data:
        return True, data[camel_name]

    return False, None


@lru_cache(maxsize=None)
def _resolve_annotations(cls: type[Any]) -> dict[str, Any]:
    try:
        return get_type_hints(cls)
    except NameError:
        return {f.name: f.type for f in fields(cls)}


def _unwrap_optional(annotation: Any) -> Any:
    if get_origin(annotation) in _UNION_ORIGINS:
        args = tuple(arg for arg in get_args(annotation) if arg is not _NoneType)
        if len(args) == 1:
            return args[0]
    return annotation


def _convert_value(annotation: Any, value: Any) -> Any:
    if value is None:
        return None

    annotation = _unwrap_optional(annotation)

    if _is_dataclass_type(annotation) and isinstance(value, dict):
        return from_dict(annotation, value)  # type: ignore[return-value]

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin in _SEQUENCE_TYPES and args and isinstance(value, (list, tuple, set, frozenset)):
        item_type = _unwrap_optional(args[0])
        return origin(_convert_value(item_type, item) for item in value)  # type: ignore[return-value]

    return value


def from_dict(cls: type[T], data: dict[str, Any]) -> T:
    """Deserialize a raw Spotify API dict into a typed dataclass instance.

    Handles snake_case ↔ camelCase conversion automatically, nested
    dataclasses recursively, and optional fields gracefully.

    Parameters
    ----------
    cls : type[T]
        A dataclass type (e.g. :class:`Track`, :class:`Artist`).
    data : dict[str, Any]
        Raw dict from the Spotify API response.

    Returns
    -------
    T
        A fully populated instance of *cls*.

    Raises
    ------
    TypeError
        If *cls* is not a dataclass, or if the data cannot be used to
        construct *cls*.

    Examples
    --------
    ::

        raw = response["data"]["searchV2"]["artists"]["items"][0]["data"]
        artist = from_dict(Artist, raw)
        print(artist.profile.name)
    """
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    annotations = _resolve_annotations(cls)
    kwargs: dict[str, Any] = {}

    for f in fields(cls):
        found, value = _extract_value(data, f.name)

        if not found:
            has_default = f.default is not MISSING or f.default_factory is not MISSING
            if not has_default:
                kwargs[f.name] = None
            continue

        kwargs[f.name] = _convert_value(annotations.get(f.name, f.type), value)

    try:
        return cls(**kwargs)
    except TypeError as exc:
        raise TypeError(f"could not construct {cls.__name__!r} from data: {exc}") from exc
