"""A small, event-loop-bound pool for asynchronous resources."""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Generic, TypeVar

__all__ = ("Pool",)

T = TypeVar("T")


class Pool(Generic[T]):
    """Reuse asynchronous resources within a single event loop.

    Active leases are unlimited. ``max_creates`` limits concurrent factory
    calls, while ``max_idle`` limits resources kept for reuse. Excess resources
    are torn down when their leases end.

    The first use binds the pool to the running event loop. Call :meth:`close`
    before stopping that loop, from outside any lease held by the calling task.
    Shutdown can overlap with other tasks' leases, but waits for them to exit.
    """

    __slots__ = (
        "_factory",
        "_teardown",
        "_max_idle",
        "_create_slots",
        "_idle",
        "_in_flight",
        "_drained",
        "_loop",
        "_close_task",
    )

    def __init__(
        self,
        factory: Callable[[], Awaitable[T]],
        teardown: Callable[[T], Awaitable[None]],
        *,
        max_idle: int = 16,
        max_creates: int = 8,
    ) -> None:
        """Initialize a pool without creating resources.

        Args:
            factory: Asynchronous callable that creates a resource.
            teardown: Asynchronous callable that disposes of a resource.
            max_idle: Maximum resources retained between leases.
            max_creates: Maximum factory calls running simultaneously.

        Raises:
            ValueError: If ``max_idle`` is negative or ``max_creates`` is
                less than one.
        """
        if type(max_idle) is not int or max_idle < 0:
            raise ValueError("max_idle must be a non-negative integer")

        if type(max_creates) is not int or max_creates < 1:
            raise ValueError("max_creates must be a positive integer")

        self._factory = factory
        self._teardown = teardown
        self._max_idle = max_idle
        self._create_slots = asyncio.Semaphore(max_creates)
        self._idle: list[T] = []
        self._in_flight = 0
        self._drained = asyncio.Event()

        self._drained.set()

        self._loop: asyncio.AbstractEventLoop | None = None
        self._close_task: asyncio.Task[None] | None = None

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<Pool idle={len(self._idle)} in_flight={self._in_flight} closed={self.closed}>"

    def _check_loop(self) -> None:
        """Bind to the first running loop and reject all other loops."""
        loop = asyncio.get_running_loop()

        if self._loop is None:
            self._loop = loop
        elif self._loop is not loop:
            raise RuntimeError("Pool belongs to another event loop")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[T, None]:
        """Lease a resource, returning it to the pool on exit when possible.

        An idle resource is reused immediately. Otherwise, a new resource is
        created, subject to the concurrent factory-call limit. A returned
        resource is disposed of if the pool is closing or the idle limit has
        been reached.

        Yields:
            A resource created by ``factory`` or reused from the pool.

        Raises:
            RuntimeError: If the pool is closing, closed, or accessed from a
                different event loop.
        """
        self._check_loop()

        if self._close_task is not None:
            raise RuntimeError("Pool is closed")

        # Count tasks waiting to create a resource as well as active leases.
        self._in_flight += 1
        self._drained.clear()

        try:
            if self._idle:
                item = self._idle.pop()
            else:
                async with self._create_slots:
                    if self._close_task is not None:
                        raise RuntimeError("Pool is closed")

                    item = self._idle.pop() if self._idle else await self._factory()

            if self._close_task is not None:
                await self._dispose(item)

                raise RuntimeError("Pool is closed")

            try:
                yield item
            finally:
                cancelled = isinstance(sys.exception(), asyncio.CancelledError)

                try:
                    if self._close_task is not None or len(self._idle) >= self._max_idle:
                        await self._dispose(item)
                    else:
                        self._idle.append(item)
                except Exception as exc:
                    if cancelled:
                        raise asyncio.CancelledError from exc

                    raise
        finally:
            self._in_flight -= 1

            if self._in_flight == 0:
                self._drained.set()

    async def _dispose(self, item: T) -> None:
        """Finish teardown even if the waiting lease is cancelled."""
        teardown_task: asyncio.Future[None] = asyncio.ensure_future(self._teardown(item))
        current = asyncio.current_task()
        cancel_count = current.cancelling() if current is not None else 0
        cancelled = False

        # Shielding alone protects the task, not the wait for its completion.
        while not teardown_task.done():
            try:
                await asyncio.shield(teardown_task)
            except asyncio.CancelledError:
                if current is not None and current.cancelling() > cancel_count:
                    cancelled = True
                    cancel_count = current.cancelling()
                elif not teardown_task.done():
                    raise
            except BaseException:
                # Observe the task's exception below, after accounting for a
                # cancellation that may have arrived at the same time.
                if current is not None and current.cancelling() > cancel_count:
                    cancelled = True

                break

        try:
            teardown_task.result()
        except BaseException as exc:
            if cancelled:
                raise asyncio.CancelledError from exc

            raise

        if cancelled:
            raise asyncio.CancelledError

    async def close(self) -> None:
        """Stop new leases, wait for existing ones, and tear down idle items.

        Concurrent calls share one shutdown operation. Cancelling a caller
        does not cancel that operation. Do not await this method while holding
        a lease in the same task, as shutdown waits for all leases to exit.
        Teardown errors from active leases propagate from ``acquire()``;
        errors from idle resources are grouped here.

        Raises:
            RuntimeError: If called from a different event loop.
            ExceptionGroup: If teardown of one or more idle resources fails.
        """
        self._check_loop()

        if self._close_task is None:
            self._close_task = asyncio.create_task(self._shutdown())

            self._close_task.add_done_callback(_observe_shutdown)

        await asyncio.shield(self._close_task)

    async def _shutdown(self) -> None:
        """Drain all leases before disposing idle resources."""
        await self._drained.wait()

        errors: list[Exception] = []

        while self._idle:
            try:
                await self._teardown(self._idle.pop())
            except Exception as exc:
                errors.append(exc)

        if errors:
            raise ExceptionGroup("Pool teardown failed", errors)

    @property
    def closed(self) -> bool:
        """Whether shutdown has finished, even if it raised an exception."""
        return self._close_task is not None and self._close_task.done()


def _observe_shutdown(task: asyncio.Task[None]) -> None:
    """Retrieve retained pool-shutdown failures without hiding them from awaiters."""
    if not task.cancelled() and (error := task.exception()) is not None:
        logging.getLogger(__name__).error("Pool shutdown failed", exc_info=error)
