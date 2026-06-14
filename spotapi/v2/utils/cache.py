from typing import Any, Callable, ParamSpec, Protocol, TypeVar, cast
import functools
import asyncio
import inspect
import time
import sys

__all__: tuple[str, ...] = ("timed_cache",)

if sys.version_info >= (3, 14):
    iscoroutinefunction = inspect.iscoroutinefunction
else:
    iscoroutinefunction = asyncio.iscoroutinefunction

P = ParamSpec("P")
R = TypeVar("R")
_R = TypeVar("_R", covariant=True)

ONE_HOUR = 60 * 60
ONE_DAY = ONE_HOUR * 24
ONE_WEEK = ONE_DAY * 7
ONE_MONTH = ONE_WEEK * 4


class _Cached(Protocol[P, _R]):
    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> _R: ...
    def cache_clear(self) -> None: ...


def timed_cache(seconds: int = ONE_DAY) -> Callable[[Callable[P, R]], _Cached[P, R]]:
    def decorator(func: Callable[..., Any]) -> Any:
        cache: dict[tuple[Any, ...], tuple[Any, float]] = {}

        def _key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Any, ...]:
            return args + tuple(sorted(kwargs.items()))

        def _fresh(ts: float) -> bool:
            return time.monotonic() - ts < seconds

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _key(args, kwargs)
            if key in cache and _fresh(cache[key][1]):
                return cache[key][0]
            result = await func(*args, **kwargs)
            cache[key] = (result, time.monotonic())
            return result

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            key = _key(args, kwargs)
            if key in cache and _fresh(cache[key][1]):
                return cache[key][0]
            result = func(*args, **kwargs)
            cache[key] = (result, time.monotonic())
            return result

        wrapper: Any = async_wrapper if iscoroutinefunction(func) else sync_wrapper
        wrapper.cache_clear = cache.clear
        return wrapper

    return cast(Callable[[Callable[P, R]], _Cached[P, R]], decorator)
