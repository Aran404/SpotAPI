from __future__ import annotations

import asyncio
import inspect
import sys
from collections import deque
from typing import Any, Callable, Coroutine, Deque, Generic, TypeVar, cast

__all__: tuple[str, ...] = ("Pool",)

if sys.version_info >= (3, 14):
    iscoroutinefunction = inspect.iscoroutinefunction
else:
    iscoroutinefunction = asyncio.iscoroutinefunction

T = TypeVar("T")


class Pool(Generic[T]):
    """A generic async-aware object pool.

    Manages a bounded collection of reusable objects, creating them on demand
    via a factory and optionally tearing them down on eviction.

    Parameters
    ----------
    factory : callable
        A sync or async callable that produces a new pool item.
    max_store : int
        Maximum number of idle items held in the pool. Defaults to ``1000``.
    max_concurrent_creates : int
        Maximum number of concurrent factory invocations permitted at once.
        Defaults to ``50``.
    teardown : callable, optional
        A sync or async callable invoked when an item is evicted from a full
        pool. Receives the evicted item as its sole argument.

    Examples
    --------
    ::

        pool: Pool[HTTPClient] = Pool(
            factory=lambda: HTTPClient(),
            teardown=lambda c: c.close(),
        )

        async def main() -> None:
            client = await pool.get()
            try:
                ...
            finally:
                pool.put(client)
    """

    __slots__: tuple[str, ...] = (
        "_factory",
        "_is_async",
        "_semaphore",
        "_store",
        "_max_store",
        "_teardown",
    )

    def __init__(
        self,
        factory: Callable[[], T] | Callable[[], Coroutine[Any, Any, T]],
        *,
        max_store: int = 1000,
        max_concurrent_creates: int = 50,
        teardown: Callable[[T], None] | Callable[[T], Coroutine[Any, Any, None]] | None = None,
    ) -> None:
        self._max_store = max_store
        self._factory = factory
        self._is_async = iscoroutinefunction(factory)
        self._semaphore = asyncio.Semaphore(max_concurrent_creates)
        self._store: Deque[T] = deque(maxlen=max_store)
        self._teardown = teardown

    async def get(self) -> T:
        """Return an idle item from the pool, creating one if empty."""
        if self._store:
            return self._store.popleft()
        return await self._create()

    def put(self, obj: T) -> None:
        """Return an item to the pool.

        If the pool is at capacity the oldest item is evicted and its teardown
        callback is scheduled before the new item is stored.
        """
        if len(self._store) == self._max_store:
            evicted = self._store.popleft()
            if self._teardown is not None:
                teardown = self._teardown
                loop = asyncio.get_running_loop()
                if iscoroutinefunction(teardown):
                    async_teardown = cast(Callable[[T], Coroutine[Any, Any, None]], teardown)
                    loop.create_task(async_teardown(evicted))
                else:
                    sync_teardown = cast(Callable[[T], None], teardown)
                    sync_teardown(evicted)
        self._store.append(obj)

    async def prewarm(self, n: int) -> None:
        """Pre-populate the pool with *n* items concurrently.

        Useful when the factory has meaningful latency (e.g. TLS handshakes)
        and you want to amortise that cost before serving requests.

        Parameters
        ----------
        n : int
            Number of items to create and store.
        """
        items = await asyncio.gather(*[self._create() for _ in range(n)])
        self._store.extend(items)

    async def _create(self) -> T:
        async with self._semaphore:
            if self._is_async:
                factory = cast(Callable[[], Coroutine[Any, Any, T]], self._factory)
                return await factory()

            factory = cast(Callable[[], T], self._factory)
            return await asyncio.get_running_loop().run_in_executor(None, factory)

    async def _teardown_all(self) -> None:
        if self._teardown is None:
            self._store.clear()
            return

        teardown = self._teardown
        if iscoroutinefunction(teardown):
            async_teardown = cast(Callable[[T], Coroutine[Any, Any, None]], teardown)
            await asyncio.gather(*[async_teardown(obj) for obj in self._store])
        else:
            sync_teardown = cast(Callable[[T], None], teardown)
            for obj in self._store:
                sync_teardown(obj)

        self._store.clear()

    async def __aenter__(self) -> Pool[T]:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._teardown_all()

    @property
    def size(self) -> int:
        """Number of idle items currently held in the pool."""
        return len(self._store)

    def __repr__(self) -> str:
        return f"<Pool size={self.size}/{self._max_store}>"
