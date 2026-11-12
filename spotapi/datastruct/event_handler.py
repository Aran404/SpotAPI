"""Asynchronous event listener registration and dispatch."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from collections.abc import Callable, Coroutine
from typing import Any, TypeAlias

from spotapi.types import DefaultLogger, LoggerProtocol

__all__ = ("EventDispatcher",)

CoroFunc: TypeAlias = Callable[..., Coroutine[Any, Any, object]]


class EventDispatcher:
    """Dispatch registered coroutine listeners in independent tasks.

    Dispatching does not wait for listeners to finish. Listener exceptions
    reach error listeners or are logged without interrupting other listeners.

    Args:
        logger: Logger used to report listener exceptions.
    """

    __slots__ = ("_listeners", "_logger", "_tasks", "_max_pending", "_closing")

    def __init__(self, logger: LoggerProtocol = DefaultLogger, *, max_pending: int = 256) -> None:
        """Initialize listener ownership and retain references to dispatched tasks."""
        if type(max_pending) is not int or max_pending < 1:
            raise ValueError("max_pending must be a positive integer")

        self._listeners: dict[str, list[CoroFunc]] = {}
        self._logger = logger
        self._tasks: set[asyncio.Task[None]] = set()
        # Bound retained callback work when listeners are slower than messages.
        self._max_pending = max_pending
        self._closing = False

    def __repr__(self) -> str:
        listeners = sum(len(callbacks) for callbacks in self._listeners.values())

        return f"<EventDispatcher listeners={listeners} running={len(self._tasks)}>"

    def register(self, coro: CoroFunc, name: str | None = None) -> None:
        """Register a coroutine function as an event listener.

        Args:
            coro: Listener to invoke when the event is dispatched.
            name: Event name. Defaults to the listener's function name.

        Raises:
            TypeError: If the listener is not a coroutine function.
            ValueError: If the listener has no function name and ``name`` is omitted.
        """
        if not inspect.iscoroutinefunction(coro):
            raise TypeError("Event registered must be a coroutine function")

        event_name = self._event_name(coro, name)

        self._listeners.setdefault(event_name, []).append(coro)

    def unregister(self, coro: CoroFunc, name: str | None = None) -> None:
        """Remove one registration of a listener, if present.

        Already scheduled tasks are unaffected.

        Args:
            coro: Previously registered listener.
            name: Event name. Defaults to the listener's function name.

        Raises:
            ValueError: If the listener has no function name and ``name`` is omitted.
        """
        event_name = self._event_name(coro, name)
        listeners = self._listeners.get(event_name)

        if listeners is None:
            return

        with contextlib.suppress(ValueError):
            listeners.remove(coro)

        if not listeners:
            del self._listeners[event_name]

    def dispatch(self, event: str, *args: object, **kwargs: object) -> None:
        """Schedule each listener for an event without waiting for it.

        Args:
            event: Name of the event to dispatch.
            *args: Positional arguments passed to each listener.
            **kwargs: Keyword arguments passed to each listener.

        Raises:
            RuntimeError: If listeners exist but no event loop is running.
        """
        listeners = self._listeners.get(event)

        if not listeners or self._closing:
            return

        loop = asyncio.get_running_loop()

        for listener in tuple(listeners):
            if len(self._tasks) >= self._max_pending:
                self._logger.warning(
                    "Event listener capacity reached; dropping callback", event=event
                )

                continue

            task = loop.create_task(
                self._execute(listener, event, *args, **kwargs),
                name=f"ws-event:{event}",
            )

            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def close(self) -> None:
        """Cancel and observe pending callbacks, preserving registrations.

        A listener may close its own socket; it is excluded from the wait to
        avoid a task awaiting itself. Dispatch resumes after shutdown.
        """
        self._closing = True

        try:
            current = asyncio.current_task()
            tasks = [task for task in self._tasks if task is not current]

            for task in tasks:
                task.cancel()

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            self._closing = False

    @staticmethod
    def _event_name(coro: CoroFunc, name: str | None) -> str:
        """Resolve an event name, requiring one for unnamed listeners."""
        if name:
            return name

        event_name = getattr(coro, "__name__", None)

        if not isinstance(event_name, str):
            raise ValueError("An explicit event name is required for unnamed listeners")

        return event_name

    async def _execute(self, coro: CoroFunc, event: str, *args: object, **kwargs: object) -> None:
        """Run a listener and report failures without suppressing cancellation."""
        try:
            await coro(*args, **kwargs)
        except Exception as exc:
            if event != "error" and self._listeners.get("error"):
                self.dispatch("error", exc)
            else:
                self._logger.error(
                    f"Unhandled exception in event handler: {event}",
                    exception=str(exc),
                )
