"""Ordered, bounded reads that preserve independent per-input failures."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar, cast

from .models.batch import BatchItem

T = TypeVar("T")


async def fetch_many(
    values: Sequence[str],
    fetch: Callable[[str], Awaitable[T]],
    *,
    concurrency: int = 8,
) -> tuple[BatchItem[T], ...]:
    """Read inputs with a bounded worker pool and return input-aligned outcomes.

    Ordinary per-input failures are captured; cancellation and other
    BaseExceptions escape. Only ``concurrency`` worker tasks are created,
    rather than scheduling a task for every item. The caller owns ``fetch``'s
    connection scope. This helper is for independent reads, never mutations.
    """
    if isinstance(values, (str, bytes)):
        raise TypeError("Pass a sequence of resource strings")
    if type(concurrency) is not int or concurrency < 1:
        raise ValueError("concurrency must be a positive integer")
    inputs = tuple(values)
    if any(not isinstance(value, str) for value in cast(tuple[object, ...], inputs)):
        raise TypeError("Batch inputs must be resource strings")
    pending = iter(enumerate(inputs))
    results: list[BatchItem[T] | None] = [None] * len(inputs)

    async def worker() -> None:
        for index, value in pending:
            try:
                result = await fetch(value)
            except Exception as error:
                results[index] = BatchItem(index, value, error=error)
            else:
                results[index] = BatchItem(index, value, result=result)

    tasks: list[asyncio.Task[None]] = []
    async with asyncio.TaskGroup() as group:
        for _ in range(min(concurrency, len(inputs))):
            tasks.append(group.create_task(worker()))
    if any(task.cancelled() for task in tasks):
        raise asyncio.CancelledError()
    return tuple(cast(BatchItem[T], item) for item in results)
