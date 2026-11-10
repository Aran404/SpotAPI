"""Small time-to-live cache decorator for synchronous and asynchronous callables."""

from __future__ import annotations

import functools
import inspect
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable, Mapping
from typing import ParamSpec, Protocol, TypeVar, cast

__all__ = ("timed_cache",)

P = ParamSpec("P")
R = TypeVar("R")
R_co = TypeVar("R_co", covariant=True)

ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4
_DEFAULT_MAX_SIZE = 256


class _Cached(Protocol[P, R_co]):
    """Callable that supports explicit cache invalidation."""

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> R_co:
        """Call the wrapped function using its preserved signature."""
        ...

    def cache_clear(self) -> None:
        """Clear cached entries and their expiration state."""
        ...


def timed_cache(
    seconds: int = ONE_DAY,
    *,
    maxsize: int | None = _DEFAULT_MAX_SIZE,
) -> Callable[[Callable[P, R]], _Cached[P, R]]:
    """Cache successful results for a fixed time-to-live.

    Async functions cache their awaited results, not coroutine objects. Each
    decorated function has its own LRU cache.

    Args:
        seconds: Cache lifetime. Values of zero or less disable cache hits.
        maxsize: Maximum retained keys. Use ``None`` for an unbounded cache or
            ``0`` to disable storage.

    Returns:
        A decorator preserving the wrapped call signature and adding
        ``cache_clear()``.

    Notes:
        Arguments must be hashable. Expired entries are removed on access;
        concurrent misses may evaluate the same key more than once. Exceptions
        are not cached.
    """
    if maxsize is not None and (type(maxsize) is not int or maxsize < 0):
        raise ValueError("maxsize must be a non-negative integer or None")

    def decorator(func: Callable[P, R]) -> _Cached[P, R]:
        """Give a callable its own bounded cache."""
        cache: OrderedDict[tuple[object, ...], tuple[object, float]] = OrderedDict()
        keyword_marker = object()

        def make_key(args: tuple[object, ...], kwargs: Mapping[str, object]) -> tuple[object, ...]:
            """Build an unambiguous, keyword-order-independent cache key."""
            if not kwargs:
                return args

            return args + (keyword_marker, *sorted(kwargs.items()))

        def get_cached(key: tuple[object, ...]) -> tuple[bool, object]:
            """Read an unexpired entry or report a cache miss."""
            entry = cache.get(key)

            if entry is None:
                return False, None

            value, created_at = entry

            if time.monotonic() - created_at >= seconds:
                del cache[key]

                return False, None

            cache.move_to_end(key)

            return True, value

        def store(key: tuple[object, ...], value: object) -> None:
            """Store one result and evict entries beyond the configured bound."""
            if maxsize == 0:
                return

            cache[key] = (value, time.monotonic())

            cache.move_to_end(key)

            if maxsize is not None and len(cache) > maxsize:
                cache.popitem(last=False)

        if inspect.iscoroutinefunction(func):
            async_func = cast(Callable[P, Awaitable[object]], func)

            @functools.wraps(func)
            async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> object:
                """Cache successful async results without caching failed or cancelled calls."""
                key = make_key(args, kwargs)
                found, value = get_cached(key)

                if found:
                    return value

                result = await async_func(*args, **kwargs)

                store(key, result)

                return result

            wrapper: Callable[P, object] = async_wrapper
        else:

            @functools.wraps(func)
            def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                """Cache successful synchronous results using the same expiration policy."""
                key = make_key(args, kwargs)
                found, value = get_cached(key)

                if found:
                    return cast(R, value)

                result = func(*args, **kwargs)

                store(key, result)

                return result

            wrapper = sync_wrapper

        # Functions support attributes; setattr keeps the original callable type.
        setattr(wrapper, "cache_clear", cache.clear)  # noqa: B010

        return cast(_Cached[P, R], wrapper)

    return decorator
