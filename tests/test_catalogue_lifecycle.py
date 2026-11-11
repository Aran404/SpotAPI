"""Public operations own their clients; explicit catalogues reuse theirs."""

from __future__ import annotations

import asyncio
from contextlib import aclosing
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import Catalogue, Public
from spotapi.catalogue import _get_many
from spotapi.datastruct import ObjectDict
from spotapi.queries import Queries
from spotapi.query import QueryClient, SharedQueryClient
from spotapi.session import AuthSession


async def test_multi_item_lookup_bounds_concurrency_and_preserves_order() -> None:
    active = peak = 0

    async def get_one(uri: str) -> str:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0)
        active -= 1
        return uri

    ids = [f"id{index}" for index in range(21)]
    assert await _get_many(ids, "track", get_one) == tuple(f"spotify:track:{id_}" for id_ in ids)
    assert peak == 8
    assert active == 0


class Client(QueryClient):
    def __init__(self) -> None:
        super().__init__(Mock(spec=AuthSession))

        self.closes = 0
        self.requests = 0
        self.failure: BaseException | None = None
        self.started = asyncio.Event()
        self.block = False

    async def pathfinder_query(
        self,
        variables: dict[str, Any],
        operation_name: str,
        *,
        max_attempts: int | None = None,
    ) -> ObjectDict:
        self.requests += 1
        self.started.set()

        if self.block:
            await asyncio.Future[None]()

        if self.failure is not None:
            raise self.failure

        return ObjectDict(
            {
                "searchV2": {
                    "tracksV2": {
                        "items": [
                            {"data": {"id": "id", "name": "Song", "uri": "spotify:track:id"}}
                        ],
                        "totalCount": 1,
                    }
                }
            }
        )

    async def close(self) -> None:
        self.closes += 1


@pytest.fixture
def clients(monkeypatch: pytest.MonkeyPatch) -> list[Client]:
    created: list[Client] = []

    async def create(*, proxy: str | None = None) -> Client:
        client = Client()

        created.append(client)

        return client

    monkeypatch.setattr(QueryClient, "create", create)

    return created


async def test_one_shot_closes_before_returning(clients: list[Client]) -> None:
    result = await Public.search("Song", types="track")

    assert result.tracks[0].name == "Song"
    assert len(clients) == 1 and clients[0].closes == 1


async def test_catalogue_reuses_client_and_rejects_calls_after_exit(clients: list[Client]) -> None:
    async with Catalogue() as catalogue:
        await asyncio.gather(*(catalogue.search("Song") for _ in range(8)))

        assert len(clients) == 1
        assert clients[0].requests == 8 and clients[0].closes == 0

    assert clients[0].closes == 1

    with pytest.raises(RuntimeError, match="not open"):
        await catalogue.search("Song")

    await catalogue.close()

    assert clients[0].closes == 1


@pytest.mark.parametrize("exhaust", [True, False])
async def test_page_exhaustion_and_explicit_close_release_transport(
    clients: list[Client], exhaust: bool
) -> None:
    async with aclosing(Public.search_tracks("Song", limit=1)) as pages:
        assert (await anext(pages))[0].name == "Song"
        assert clients[0].closes == 0

        if exhaust:
            assert await anext(pages, None) is None

    assert clients[0].closes == 1


async def test_request_failure_still_closes_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Client()
    client.failure = ValueError("broken response")

    monkeypatch.setattr(QueryClient, "create", AsyncMock(return_value=client))

    with pytest.raises(ValueError, match="broken response"):
        await Public.search("Song")

    assert client.closes == 1


async def test_cancelled_request_closes_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    client = Client()
    client.block = True

    async def create() -> Client:
        return client

    monkeypatch.setattr(QueryClient, "create", create)

    request = asyncio.create_task(Public.search("Song"))

    await client.started.wait()
    request.cancel()

    with pytest.raises(asyncio.CancelledError):
        await request

    assert client.closes == 1


async def test_injected_queries_remain_owned_by_the_caller(clients: list[Client]) -> None:
    owner = SharedQueryClient()

    try:
        async with Catalogue(queries=Queries(owner)) as catalogue:
            await catalogue.search("Song")

        assert not owner.closed
        assert clients[0].closes == 0
    finally:
        await owner.close()

    assert clients[0].closes == 1
