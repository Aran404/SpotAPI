from __future__ import annotations

import types
from functools import lru_cache
from dataclasses import MISSING, fields, is_dataclass
from typing import Any, TypeVar, Union, get_args, get_origin, TypeGuard, get_type_hints

from v2.specialized.data_wrappers.playlist import Playlist
from v2.specialized.data_wrappers.track import Track
from v2.specialized.data_wrappers.artist import Artist
from v2.specialized.data_wrappers.podcast import Podcast
from v2.specialized.data_wrappers.album import Album

__all__: tuple[str, ...] = (
    "Track",
    "Playlist",
    "Artist",
    "Podcast",
    "Album",
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
        return from_dict(annotation, value)

    origin = get_origin(annotation)
    args = get_args(annotation)

    if (
        origin in _SEQUENCE_TYPES
        and args
        and isinstance(value, (list, tuple, set, frozenset))
    ):
        item_type = _unwrap_optional(args[0])
        return origin(_convert_value(item_type, item) for item in value)

    return value


def from_dict(cls: type[T], data: dict[str, Any]) -> T:
    if not is_dataclass(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    annotations = _resolve_annotations(cls)
    kwargs: dict[str, Any] = {}

    for f in fields(cls):
        found, value = _extract_value(data, f.name)

        if not found:
            has_default = f.default is not MISSING or f.default_factory is not MISSING  # type: ignore[misc]
            if not has_default:
                kwargs[f.name] = None
            continue

        kwargs[f.name] = _convert_value(annotations.get(f.name, f.type), value)

    try:
        return cls(**kwargs)
    except TypeError as exc:
        raise TypeError(
            f"could not construct {cls.__name__!r} from data: {exc}"
        ) from exc
