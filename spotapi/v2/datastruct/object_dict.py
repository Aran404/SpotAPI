from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from typing import Any, TypeVar, overload

__all__: tuple[str, ...] = ("ObjectDict",)

_T = TypeVar("_T")


class ObjectDict(dict[Any, Any]):
    """
    Wraps a dictionary in an object-like interface, allowing keys to be accessed as attributes.
    """

    __slots__: tuple[str, ...] = ("_lock",)

    def __init__(
        self,
        m: Mapping[Any, Any] | None = None,
        /,
        *,
        lock_attribute_writes: bool = False,
        **kwargs: Any,
    ) -> None:
        object.__setattr__(self, "_lock", threading.Lock() if lock_attribute_writes else None)

        data = dict(m or {})
        data.update(kwargs)
        super().__init__(
            {
                (f"_{k}" if isinstance(k, str) and k in dict.__dict__ else k): self._wrap(v)
                for k, v in data.items()
            }
        )

    @overload
    @classmethod
    def from_json(
        cls: type[ObjectDict],
        data: dict[Any, Any],
        *,
        lock_attribute_writes: bool = ...,
    ) -> ObjectDict: ...

    @overload
    @classmethod
    def from_json(
        cls: type[ObjectDict],
        data: list[Any],
        *,
        lock_attribute_writes: bool = ...,
    ) -> list[Any]: ...

    @overload
    @classmethod
    def from_json(
        cls: type[ObjectDict],
        data: tuple[Any, ...],
        *,
        lock_attribute_writes: bool = ...,
    ) -> tuple[Any, ...]: ...

    @overload
    @classmethod
    def from_json(cls: type[ObjectDict], data: _T, *, lock_attribute_writes: bool = ...) -> _T: ...

    @classmethod
    def from_json(
        cls: type[ObjectDict],
        data: Any,
        *,
        lock_attribute_writes: bool = False,
    ) -> Any:
        if isinstance(data, dict):
            return cls(data, lock_attribute_writes=lock_attribute_writes)  # type: ignore[reportUnknownArgumentType]
        if isinstance(data, list):
            return [
                cls.from_json(item, lock_attribute_writes=lock_attribute_writes)  # type: ignore[reportUnknownArgumentType]
                for item in data
            ]
        if isinstance(data, tuple):
            return tuple(
                cls.from_json(item, lock_attribute_writes=lock_attribute_writes)  # type: ignore[reportUnknownArgumentType]
                for item in data
            )
        return data

    def _is_locked(self) -> bool:
        return object.__getattribute__(self, "_lock") is not None

    def _wrap(self, value: Any) -> Any:
        if isinstance(value, list):
            return [self._wrap(v) for v in value]  # type: ignore[reportUnknownArgumentType]
        if isinstance(value, tuple):
            return tuple(self._wrap(v) for v in value)  # type: ignore[reportUnknownArgumentType]
        if isinstance(value, dict) and not isinstance(value, ObjectDict):
            return ObjectDict(value, lock_attribute_writes=self._is_locked())  # type: ignore[reportUnknownArgumentType]
        return value

    @classmethod
    def _unwrap(cls, value: Any) -> Any:
        """Recursively converts ObjectDict instances and containers back to standard Python types."""
        if isinstance(value, ObjectDict):
            return value.to_dict()
        if isinstance(value, list):
            return [cls._unwrap(v) for v in value]
        if isinstance(value, tuple):
            return tuple(cls._unwrap(v) for v in value)
        if isinstance(value, dict):
            return {  # type: ignore[reportUnknownArgumentType]
                (
                    k[1:]
                    if isinstance(k, str) and k.startswith("_") and k[1:] in dict.__dict__
                    else k
                ): cls._unwrap(v)
                for k, v in value.items()
            }
        return value

    def to_dict(self) -> dict[Any, Any]:
        """Converts the entire nested ObjectDict into standard dicts and primitives."""
        return {
            (
                k[1:] if isinstance(k, str) and k.startswith("_") and k[1:] in dict.__dict__ else k
            ): self._unwrap(v)
            for k, v in super().items()
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    # Override dictionary iteration methods so dict(obj) constructs a clean dict recursively
    def items(self) -> Any:
        return self.to_dict().items()

    def values(self) -> Any:
        return self.to_dict().values()

    def __iter__(self) -> Any:
        return iter(super().keys())

    def __getattr__(self, name: str) -> Any:
        try:
            return self[name]
        except KeyError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            ) from None

    def __setattr__(self, name: str, value: Any) -> None:
        if name in type(self).__slots__:
            object.__setattr__(self, name, value)
            return

        lock: threading.Lock | None = object.__getattribute__(self, "_lock")
        processed = self._wrap(value)

        if lock is not None:
            with lock:
                self[name] = processed
        else:
            self[name] = processed

    def __delattr__(self, name: str) -> None:
        try:
            del self[name]
        except KeyError:
            raise AttributeError(
                f"'{type(self).__name__}' object has no attribute '{name}'"
            ) from None

    def __repr__(self) -> str:
        return f"{type(self).__name__}({super().__repr__()})"
