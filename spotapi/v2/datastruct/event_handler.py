from __future__ import annotations

import sys
import asyncio
import inspect
import contextlib
from typing import TYPE_CHECKING, Any, Callable, Coroutine, TypeAlias, TypeVar

if TYPE_CHECKING:
    from spotapi.v2.types import LoggerProtocol

__all__: tuple[str, ...] = ("EventDispatcher",)

if sys.version_info >= (3, 14):
    iscoroutinefunction = inspect.iscoroutinefunction
else:
    iscoroutinefunction = asyncio.iscoroutinefunction

T = TypeVar("T")
Coro: TypeAlias = Coroutine[Any, Any, T]
CoroFunc: TypeAlias = Callable[..., Coro[Any]]


class EventDispatcher:
    __slots__: tuple[str, ...] = (
        "_listeners",
        "_logger",
    )

    def __init__(self, logger: LoggerProtocol) -> None:
        self._listeners: dict[str, list[CoroFunc]] = {}
        self._logger = logger

    def register(self, coro: CoroFunc, name: str | None = None) -> None:
        if not iscoroutinefunction(coro):
            raise TypeError("Event registered must be a coroutine function")

        event_name = name or coro.__name__
        self._listeners.setdefault(event_name, []).append(coro)

    def unregister(self, coro: CoroFunc, name: str | None = None) -> None:
        event_name = name or coro.__name__
        if event_name in self._listeners:
            with contextlib.suppress(ValueError):
                self._listeners[event_name].remove(coro)

    def dispatch(self, event: str, *args: Any, **kwargs: Any) -> None:
        for listener in self._listeners.get(event, []):
            asyncio.create_task(
                self._execute(listener, event, *args, **kwargs),
                name=f"ws-event:{event}",
            )

    async def _execute(self, coro: CoroFunc, event: str, *args: Any, **kwargs: Any) -> None:
        try:
            await coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            self._logger.debug(
                f"Unhandled exception in event handler: {event}", exception=str(exc)
            )
