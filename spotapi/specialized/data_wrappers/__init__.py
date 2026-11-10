"""Typed Spotify response models and a small, strict dataclass decoder."""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import MISSING, fields, is_dataclass
from functools import lru_cache
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

from .album import Album
from .album_details import AlbumDetails
from .artist import Artist
from .artist_details import ArtistDetails
from .catalogue import (
    Audiobook,
    Author,
    Episode,
    Genre,
    PodcastDetails,
    PublicProfile,
    User,
)
from .common import (
    ColorDark,
    ExtractedColors,
    ExtractedColorSet,
    Sources,
    SquareCoverImage,
    VisualIdentity,
)
from .playlist import Playlist
from .playlist_details import PlaylistDetails, PlaylistEntry
from .playlist_track import PlaylistTrack
from .podcast import Podcast
from .podcast_episode import PodcastEpisodeDetails
from .profile_attributes import Profile
from .track import Track
from .track_details import TrackDetails

__all__ = (
    "Audiobook",
    "Author",
    "Episode",
    "Genre",
    "PodcastDetails",
    "PublicProfile",
    "User",
    "PlaylistDetails",
    "PlaylistEntry",
    "Track",
    "Playlist",
    "Artist",
    "ArtistDetails",
    "Podcast",
    "PodcastEpisodeDetails",
    "Album",
    "Profile",
    "TrackDetails",
    "AlbumDetails",
    "PlaylistTrack",
    "Sources",
    "ColorDark",
    "ExtractedColors",
    "VisualIdentity",
    "SquareCoverImage",
    "ExtractedColorSet",
    "from_dict",
)

T = TypeVar("T")
_UNION_ORIGINS = (Union, types.UnionType)


def _is_dataclass_type(value: object) -> bool:
    """Identify dataclass classes, excluding dataclass instances."""
    return isinstance(value, type) and is_dataclass(value)


def _camel_case(name: str) -> str:
    """Convert a Python field name to a GraphQL response key."""
    first, *rest = name.split("_")

    return first + "".join(part.capitalize() for part in rest)


def _field_value(data: Mapping[str, Any], name: str) -> tuple[bool, Any]:
    """Resolve snake_case, camelCase and ObjectDict-escaped keys."""
    alias = _camel_case(name)

    for key in (name, alias):
        if key in data:
            return True, data[key]

    return False, None


@lru_cache(maxsize=256)
def _annotations(cls: type[Any]) -> dict[str, Any]:
    """Resolve postponed dataclass annotations once per model."""
    return get_type_hints(cls)


def _decode(annotation: Any, value: Any, path: str) -> Any:
    """Decode one annotated value without silently discarding errors."""
    if annotation is Any or annotation is object:
        return value

    origin = get_origin(annotation)

    if origin in _UNION_ORIGINS:
        options = get_args(annotation)

        if value is None and type(None) in options:
            return None

        for option in options:
            if option is type(None):
                continue

            try:
                return _decode(option, value, path)
            except (TypeError, ValueError):
                continue

        raise TypeError(f"{path}: value does not match {annotation!r}")

    if value is None:
        raise TypeError(f"{path}: expected {annotation!r}, got None")

    if _is_dataclass_type(annotation):
        if not isinstance(value, Mapping):
            raise TypeError(f"{path}: expected an object, got {type(value).__name__}")

        return _from_dict(
            cast(type[Any], annotation),
            cast(Mapping[str, Any], value),
            path,
        )

    if origin in (list, tuple, set, frozenset):
        if not isinstance(value, (list, tuple, set, frozenset)):
            raise TypeError(f"{path}: expected a sequence")

        args: tuple[Any, ...] = get_args(annotation)
        item_type = next(iter(args), None)

        if item_type is None:
            raise TypeError(f"{path}: sequence field must declare an item type")

        elements = cast(
            list[object] | tuple[object, ...] | set[object] | frozenset[object],
            value,
        )

        if origin is tuple and len(args) > 1 and args[-1] is not Ellipsis:
            if len(elements) != len(args):
                raise ValueError(f"{path}: tuple length does not match annotation")

            items = [
                _decode(arg, item, f"{path}[{index}]")
                for index, (arg, item) in enumerate(zip(args, elements, strict=True))
            ]
        else:
            items = [
                _decode(item_type, item, f"{path}[{index}]") for index, item in enumerate(elements)
            ]

        if origin is tuple:
            return tuple(items)

        if origin is set:
            return set(items)

        if origin is frozenset:
            return frozenset(items)

        return items

    if origin is dict:
        if not isinstance(value, Mapping):
            raise TypeError(f"{path}: expected a mapping")

        key_type, value_type = cast(tuple[Any, Any], get_args(annotation))
        source = cast(Mapping[object, object], value)

        return {
            _decode(key_type, key, f"{path}.key"): _decode(value_type, item, f"{path}[{key!r}]")
            for key, item in source.items()
        }

    if annotation is bool:
        if type(value) is not bool:
            raise TypeError(f"{path}: expected bool")
    elif annotation is int:
        if type(value) is not int:
            raise TypeError(f"{path}: expected int")
    elif annotation is float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{path}: expected float")

        return float(value)
    elif annotation is str and not isinstance(value, str):
        raise TypeError(f"{path}: expected str")

    return value


def _from_dict(cls: type[T], data: Mapping[str, Any], path: str) -> T:
    """Decode annotated nested dataclasses, preserving optional fields and aliases."""
    annotations = _annotations(cls)
    values: dict[str, Any] = {}

    for model_field in fields(cast(Any, cls)):
        if not model_field.init:
            continue

        name = model_field.name
        present, value = _field_value(data, name)

        if present:
            values[name] = _decode(annotations[name], value, f"{path}.{name}")
        elif model_field.default is MISSING and model_field.default_factory is MISSING:
            raise ValueError(f"{path}.{name}: required field is missing")

    return cls(**values)


def from_dict(cls: type[T], data: object) -> T:
    """Deserialize a mapping into a typed dataclass.

    Keys may use Python snake_case or Spotify camelCase. Unknown keys are
    ignored, and optional/default fields may be absent. Present values are
    validated recursively rather than silently replaced with ``None``.

    Args:
        cls: Target dataclass type.
        data: Spotify response object.

    Returns:
        The recursively populated dataclass.

    Raises:
        TypeError: A supplied value has the wrong type.
        ValueError: A required field is missing.
    """
    if not _is_dataclass_type(cls):
        raise TypeError(f"{cls!r} is not a dataclass")

    if not isinstance(data, Mapping):
        raise TypeError(f"{cls.__name__}: expected an object")

    return _from_dict(cls, cast(Mapping[str, Any], data), cls.__name__)
