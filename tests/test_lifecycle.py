"""Cancellation and ownership tests independent of Spotify availability."""

from __future__ import annotations

import asyncio

import pytest

from spotapi.v2 import query
from spotapi.v2.datastruct import EventDispatcher, Pool
from spotapi.v2.query import SharedQueryClient


async def test_concurrent_queries_share_one_initialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    creates = 0
    closes = 0
    entered = 0
    all_entered = asyncio.Event()
    instance = object()

    async def create():
        nonlocal creates
        creates += 1

        await asyncio.sleep(0)

        return instance

    async def close() -> None:
        nonlocal closes
        closes += 1

    class Client:
        async def close(self) -> None:
            await close()

    instance = Client()

    monkeypatch.setattr(query.QueryClient, "create", create)

    owner = SharedQueryClient()

    async def borrow() -> None:
        nonlocal entered

        async with owner.acquire() as client:
            assert client is instance
            entered += 1

            if entered == 20:
                all_entered.set()

            await asyncio.wait_for(all_entered.wait(), 1)

    await asyncio.gather(*(borrow() for _ in range(20)))
    await asyncio.gather(owner.close(), owner.close())

    assert creates == closes == 1


async def test_shared_close_waits_for_requests_and_rejects_new_leases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = asyncio.Event()

    class Client:
        async def close(self) -> None:
            closed.set()

    async def create():
        return Client()

    monkeypatch.setattr(query.QueryClient, "create", create)

    owner = SharedQueryClient()

    async with owner.acquire():
        shutdown = asyncio.create_task(owner.close())

        await asyncio.sleep(0)

        assert not closed.is_set()

        with pytest.raises(RuntimeError, match="closed"):
            async with owner.acquire():
                pass

    await shutdown

    assert closed.is_set()


async def test_cancelled_initialization_can_be_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()
    cleaned = asyncio.Event()
    calls = 0

    class Client:
        async def close(self) -> None:
            pass

    async def create():
        nonlocal calls
        calls += 1

        if calls == 1:
            started.set()

            try:
                await asyncio.Future()
            finally:
                cleaned.set()

        return Client()

    monkeypatch.setattr(query.QueryClient, "create", create)

    owner = SharedQueryClient()

    async def borrow() -> None:
        async with owner.acquire():
            pass

    task = asyncio.create_task(borrow())

    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert cleaned.is_set()

    await borrow()
    await owner.close()

    assert calls == 2


async def test_cancelled_close_waiter_does_not_cancel_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    finish = asyncio.Event()
    closed = asyncio.Event()

    class Client:
        async def close(self) -> None:
            started.set()
            await finish.wait()
            closed.set()

    async def create():
        return Client()

    monkeypatch.setattr(query.QueryClient, "create", create)

    owner = SharedQueryClient()

    async with owner.acquire():
        pass

    task = asyncio.create_task(owner.close())

    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    finish.set()
    await owner.close()

    assert closed.is_set()


async def test_pool_preserves_cancellation_when_teardown_fails() -> None:
    started = asyncio.Event()

    async def create():
        return object()

    async def teardown(item: object) -> None:
        raise ValueError("cleanup failed")

    pool = Pool(create, teardown, max_idle=0)

    async def borrow() -> None:
        async with pool.acquire():
            started.set()
            await asyncio.Future()

    task = asyncio.create_task(borrow())

    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError) as raised:
        await task

    assert isinstance(raised.value.__cause__, ValueError)

    await pool.close()


async def test_pool_waiter_cancellation_and_idle_teardown_errors() -> None:
    started = asyncio.Event()
    proceed = asyncio.Event()

    async def create():
        started.set()
        await proceed.wait()

        return object()

    async def teardown(item: object) -> None:
        raise ValueError("close failure")

    pool = Pool(create, teardown, max_creates=1)

    async def borrow() -> None:
        async with pool.acquire():
            pass

    first = asyncio.create_task(borrow())

    await started.wait()

    waiter = asyncio.create_task(borrow())

    await asyncio.sleep(0)
    waiter.cancel()

    with pytest.raises(asyncio.CancelledError):
        await waiter

    proceed.set()
    await first

    with pytest.raises(ExceptionGroup) as raised:
        await pool.close()

    assert len(raised.value.exceptions) == 1
    assert pool.closed


async def test_event_tasks_are_bounded_and_drained() -> None:
    events = EventDispatcher(max_pending=2)
    started = asyncio.Event()
    cancelled: list[bool] = []

    async def slow() -> None:
        started.set()

        try:
            await asyncio.Future()
        finally:
            cancelled.append(True)

    events.register(slow, "message")

    for _ in range(50):
        events.dispatch("message")

    assert len(events._tasks) == 2

    await started.wait()
    await events.close()

    assert len(cancelled) == 2
    assert not events._tasks


def test_implicit_clients_are_isolated_and_cleaned_across_loops() -> None:
    owners: list[SharedQueryClient] = []

    async def run() -> None:
        owner = query.query_client_pool()

        owners.append(owner)

        assert query.query_client_pool() is owner

    asyncio.run(run())
    asyncio.run(run())

    assert owners[0] is not owners[1]
    assert all(owner.closed for owner in owners)
    assert not query._registry.entries


async def test_listener_can_close_its_dispatcher() -> None:
    events = EventDispatcher()
    finished = asyncio.Event()

    async def listener() -> None:
        await events.close()
        finished.set()

    events.register(listener)
    events.dispatch("listener")
    await asyncio.wait_for(finished.wait(), 1)
    await events.close()
