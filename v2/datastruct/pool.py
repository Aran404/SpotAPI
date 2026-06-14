from __future__ import annotations

from typing import Generic, TypeVar, Callable, Deque, Coroutine, Any, cast
from collections import deque
import asyncio
import inspect
import sys

__all__: tuple[str, ...] = ("Pool",)

if sys.version_info >= (3, 14):
    iscoroutinefunction = inspect.iscoroutinefunction
else:
    iscoroutinefunction = asyncio.iscoroutinefunction

T = TypeVar("T")


class Pool(Generic[T]):
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
        teardown: (
            Callable[[T], None] | Callable[[T], Coroutine[Any, Any, None]] | None
        ) = None,
    ) -> None:
        self._max_store = max_store
        self._factory = factory
        self._is_async = iscoroutinefunction(factory)
        self._semaphore = asyncio.Semaphore(max_concurrent_creates)
        self._store: Deque[T] = deque(maxlen=max_store)
        self._teardown = teardown

    async def get(self) -> T:
        if self._store:
            return self._store.popleft()
        return await self._create()

    def put(self, obj: T) -> None:
        if len(self._store) == self._max_store:
            evicted = self._store.popleft()
            loop = asyncio.get_event_loop()
            if self._teardown is not None:
                teardown = self._teardown
                if iscoroutinefunction(teardown):
                    async_teardown = cast(
                        Callable[[T], Coroutine[Any, Any, None]], teardown
                    )
                    loop.create_task(async_teardown(evicted))
                else:
                    sync_teardown = cast(Callable[[T], None], teardown)
                    sync_teardown(evicted)
        self._store.append(obj)

    async def prewarm(self, n: int) -> None:
        """prewarn gathers multiple [n] concurrently (Useful for factories that have latency for result)"""
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
        return len(self._store)
