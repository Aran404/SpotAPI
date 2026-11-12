"""Attribute-accessible JSON mappings."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from typing import Any, Final, Protocol, Self, TypeAlias, TypeVar, cast, overload

__all__ = ("ObjectDict",)

_ValueT_co = TypeVar("_ValueT_co", covariant=True)


class _SupportsKeysAndGetItem(Protocol[_ValueT_co]):
    """A mapping-like object with string keys and indexed values."""

    def keys(self) -> Iterable[str]:
        """Return mapping keys without attribute-name collisions."""
        ...

    def __getitem__(self, key: str, /) -> _ValueT_co:
        """Read a mapping value by its original JSON key."""
        ...


_UpdateSource: TypeAlias = _SupportsKeysAndGetItem[Any] | Iterable[tuple[str, Any]]


_SHADOWED: Final = frozenset(
    {name for name in dir(dict) if not name.startswith("__")} | {"from_json", "to_dict", "to_json"}
)


def _mapping_key(name: str) -> str:
    """Return the JSON key represented by an escaped attribute name."""
    if name.startswith("_") and (name[1:] in _SHADOWED or name[1:].startswith("_")):
        return name[1:]

    return name


def _wrap(value: object) -> Any:
    """Recursively wrap JSON containers for attribute access."""
    if isinstance(value, ObjectDict):
        return value

    if isinstance(value, dict):
        return ObjectDict(cast(dict[str, object], value))

    if isinstance(value, list):
        return [_wrap(item) for item in cast(list[object], value)]

    if isinstance(value, tuple):
        return tuple(_wrap(item) for item in cast(tuple[object, ...], value))

    return value


def _unwrap(value: object) -> Any:
    """Recursively convert wrapped containers to plain Python containers."""
    if isinstance(value, ObjectDict):
        return value.to_dict()

    if isinstance(value, dict):
        mapping = cast(dict[str, object], value)

        return {key: _unwrap(item) for key, item in mapping.items()}

    if isinstance(value, list):
        return [_unwrap(item) for item in cast(list[object], value)]

    if isinstance(value, tuple):
        return tuple(_unwrap(item) for item in cast(tuple[object, ...], value))

    return value


class ObjectDict(dict[str, Any]):
    """A ``dict`` with attribute access to keys that do not shadow methods.

    JSON keys remain unchanged for normal mapping operations. Conflicting
    attribute names gain an underscore: ``{"items": []}`` is available as
    ``data._items``. Use :meth:`to_dict` to recursively unwrap nested values.
    """

    __slots__ = ()

    def __init__(self, m: _UpdateSource | None = None, /, **kwargs: Any) -> None:
        """Recursively wrap nested mappings while preserving ordinary mapping access."""
        super().__init__()

        if m is not None:
            self.update(m)

        if kwargs:
            self.update(kwargs)

    @overload
    @staticmethod
    def from_json(data: dict[str, Any]) -> ObjectDict: ...

    @overload
    @staticmethod
    def from_json(data: list[dict[str, Any]]) -> list[ObjectDict]: ...

    @overload
    @staticmethod
    def from_json(data: object) -> Any: ...

    @staticmethod
    def from_json(data: Any) -> Any:
        """Wrap a parsed JSON value recursively."""
        return _wrap(data)

    def __setitem__(self, key: str, value: Any) -> None:
        """Store a value, recursively wrapping nested JSON containers."""
        super().__setitem__(key, _wrap(value))

    def update(
        self,
        m: _UpdateSource = (),
        /,
        **kwargs: Any,
    ) -> None:
        """Update keys while keeping nested mappings attribute-accessible."""
        if isinstance(m, Mapping):
            source = cast(Mapping[str, Any], m)

            for key, value in source.items():
                self[key] = value
        elif callable(getattr(m, "keys", None)) and hasattr(m, "__getitem__"):
            source = cast(_SupportsKeysAndGetItem[Any], m)
            keys = source.keys()

            for key in keys:
                self[key] = source[key]
        else:
            for key, value in cast(Iterable[tuple[str, Any]], m):
                self[key] = value

        for key, value in kwargs.items():
            self[key] = value

    def setdefault(self, key: str, default: Any = None) -> Any:
        """Return a key's value, inserting a wrapped default when absent."""
        try:
            return super().__getitem__(key)
        except KeyError:
            self[key] = default

            return super().__getitem__(key)

    def __ior__(
        self,
        other: _UpdateSource,
        /,
    ) -> Self:
        """Update this mapping in place while retaining nested attribute access."""
        self.update(other)

        return self

    def to_dict(self) -> dict[str, Any]:
        """Return a deep copy using the original JSON keys."""
        return {key: _unwrap(value) for key, value in super().items()}

    def to_json(self) -> str:
        """Serialize the original JSON keys and nested values."""
        return json.dumps(self.to_dict())

    def __getattr__(self, name: str) -> Any:
        """Resolve a non-shadowing JSON key through attribute access."""
        key = _mapping_key(name)

        try:
            return super().__getitem__(key)
        except KeyError:
            message = f"{type(self).__name__!r} object has no attribute {name!r}"
            raise AttributeError(message, name=name, obj=self) from None

    def __setattr__(self, name: str, value: Any) -> None:
        """Store an escaped attribute name as its corresponding JSON key."""
        self[_mapping_key(name)] = value

    def __delattr__(self, name: str) -> None:
        """Delete the JSON key represented by this attribute name."""
        key = _mapping_key(name)

        try:
            super().__delitem__(key)
        except KeyError:
            message = f"{type(self).__name__!r} object has no attribute {name!r}"
            raise AttributeError(message, name=name, obj=self) from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({super().__repr__()})"
