"""Decode Spotify response mappings into typed dataclasses."""

from __future__ import annotations

import types
from collections.abc import Mapping
from dataclasses import MISSING, fields, is_dataclass
from functools import lru_cache
from typing import Any, TypeVar, Union, cast, get_args, get_origin, get_type_hints

T = TypeVar("T")
_UNION_ORIGINS = (Union, types.UnionType)


def _is_dataclass_type(value: object) -> bool:
    """Identify dataclass classes, excluding dataclass instances."""
    return isinstance(value, type) and is_dataclass(value)


def field_alias(name: str) -> str:
    """Map Python field names to Spotify keys, including GraphQL metadata."""
    if name == "_typename":
        return "__typename"

    first, *rest = name.split("_")

    return first + "".join(part.capitalize() for part in rest)


def _field_value(data: Mapping[str, Any], name: str) -> tuple[bool, Any]:
    """Resolve Python field names and their corresponding Spotify keys."""
    alias = field_alias(name)

    for key in (name, alias):
        if key in data:
            return True, data[key]

    return False, None


def required_fields(typ: type | None) -> dict[str, str]:
    """Map required dataclass fields to the same aliases used during decoding."""
    if typ is None or not is_dataclass(typ):
        return {}

    return {
        item.name: field_alias(item.name)
        for item in fields(typ)
        if item.init and item.default is MISSING and item.default_factory is MISSING
    }


@lru_cache(maxsize=256)
def _annotations(cls: type[Any]) -> dict[str, Any]:
    """Resolve postponed dataclass annotations once per model."""
    return get_type_hints(cls)


def _decode_union(annotation: Any, value: Any, path: str) -> Any:
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


def _decode_sequence(annotation: Any, value: Any, path: str) -> Any:
    if not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError(f"{path}: expected a sequence")

    args: tuple[Any, ...] = get_args(annotation)
    item_type = next(iter(args), None)
    if item_type is None:
        raise TypeError(f"{path}: sequence field must declare an item type")

    origin = get_origin(annotation)
    elements = cast(list[object] | tuple[object, ...] | set[object] | frozenset[object], value)
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


def _decode_scalar(annotation: Any, value: Any, path: str) -> Any:
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


def _decode(annotation: Any, value: Any, path: str) -> Any:
    if annotation is Any or annotation is object:
        return value

    origin = get_origin(annotation)
    if origin in _UNION_ORIGINS:
        return _decode_union(annotation, value, path)
    if value is None:
        raise TypeError(f"{path}: expected {annotation!r}, got None")
    if _is_dataclass_type(annotation):
        if not isinstance(value, Mapping):
            raise TypeError(f"{path}: expected an object, got {type(value).__name__}")
        return _from_dict(cast(type[Any], annotation), cast(Mapping[str, Any], value), path)
    if origin in (list, tuple, set, frozenset):
        return _decode_sequence(annotation, value, path)
    if origin is dict:
        if not isinstance(value, Mapping):
            raise TypeError(f"{path}: expected a mapping")
        key_type, value_type = cast(tuple[Any, Any], get_args(annotation))
        source = cast(Mapping[object, object], value)
        return {
            _decode(key_type, key, f"{path}.key"): _decode(value_type, item, f"{path}[{key!r}]")
            for key, item in source.items()
        }
    return _decode_scalar(annotation, value, path)


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
