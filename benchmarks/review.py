"""Reproducible overhead and opt-in live catalogue benchmarks.

Run from the root: python benchmarks/review.py --output benchmarks/offline.json
Add --live for real Spotify traffic. No credentials or mutations are used.
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import hashlib
import json
import math
import platform
import statistics
import subprocess
import tempfile
import time
import tracemalloc
from collections.abc import Awaitable, Callable, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, Unpack, cast
from unittest.mock import patch

import wreq

from spotapi import Catalogue, Public, close_query_clients
from spotapi.connection.http import HTTPClient
from spotapi.connection.types import Methods, Response
from spotapi.datastruct import ObjectDict, Pool
from spotapi.models.catalogue import Track, from_dict
from spotapi.queries import Queries
from spotapi.query import QueryClient, SharedQueryClient
from spotapi.session import QueryCache


class Options(argparse.Namespace):
    live: bool
    samples: int
    output: str | None


class LegacySearch(Protocol):
    def __call__(
        self, instance: SimpleNamespace, query: str, *, limit: int
    ) -> Mapping[str, Any]: ...


def summary(samples: Sequence[float]) -> dict[str, object]:
    ordered = sorted(samples)

    return {
        "samples_ms": [round(value * 1000, 4) for value in samples],
        "p50_ms": round(statistics.median(ordered) * 1000, 4),
        "p95_ms": round(ordered[math.ceil(len(ordered) * 0.95) - 1] * 1000, 4),
    }


async def timed(call: Callable[[], Awaitable[object]]) -> float:
    start = time.perf_counter()

    await call()

    return time.perf_counter() - start


async def offline_owner(shared: bool) -> dict[str, object]:
    creates = closes = requests = 0
    payload = ObjectDict(
        {
            "searchV2": {
                "tracksV2": {
                    "items": [
                        {
                            "data": {
                                "id": "example",
                                "name": "Example",
                                "uri": "spotify:track:example",
                            }
                        }
                    ]
                }
            }
        }
    )

    class Client(QueryClient):
        def __init__(self) -> None:
            pass

        async def pathfinder_query(
            self,
            variables: dict[str, Any],
            operation_name: str,
            *,
            max_attempts: int | None = None,
        ) -> ObjectDict:
            nonlocal requests
            requests += 1

            await asyncio.sleep(0)

            return payload

        async def close(self) -> None:
            nonlocal closes
            closes += 1

    async def create() -> QueryClient:
        nonlocal creates
        creates += 1

        await asyncio.sleep(0)

        return Client()

    async def search() -> None:
        result = await catalogue.search("Example", types="track", limit=1)

        assert result.tracks[0].name == "Example"

    async def destroy(client: QueryClient) -> None:
        await client.close()

    with patch.object(QueryClient, "create", create):
        owner = SharedQueryClient() if shared else Pool(create, destroy)

        async with Catalogue(queries=Queries(owner)) as catalogue:
            # Start with a burst: this reproduces the common startup fan-out.
            burst = await timed(lambda: asyncio.gather(*(search() for _ in range(32))))

            startup_creates = creates
            warm = [await timed(search) for _ in range(100)]

        await owner.close()

    return {
        "startup_burst_32_ms": round(burst * 1000, 4),
        "startup_clients_created": startup_creates,
        "total_clients_created": creates,
        "total_clients_closed": closes,
        "logical_query_requests": requests,
        "warm": summary(warm),
    }


def decode_benchmark() -> dict[str, object]:
    payload = {
        "id": "example",
        "name": "Example",
        "uri": "spotify:track:example",
        "artists": {"items": [{"uri": "spotify:artist:example", "profile": {"name": "Artist"}}]},
    }

    from_dict(Track, payload)

    samples: list[float] = []

    for _ in range(20):
        start = time.perf_counter()

        for _ in range(1000):
            from_dict(Track, payload)

        samples.append((time.perf_counter() - start) / 1000)

    tracemalloc.start()

    models = [from_dict(Track, payload) for _ in range(1000)]
    current, peak = tracemalloc.get_traced_memory()

    tracemalloc.stop()

    assert len(models) == 1000

    return {
        **summary(samples),
        "retained_1000_models_bytes": current,
        "peak_bytes": peak,
    }


def legacy_search_overhead() -> dict[str, object]:
    """Run the real v1 query builder from Git with only its transport replaced.

    v1 returns raw data; v2 builds typed models. Both benchmark consumers read
    the same track name. This measures client work, never network speed.
    """
    root = Path(__file__).resolve().parents[1]
    revision = subprocess.run(
        ["git", "log", "-1", "--format=%H", "--diff-filter=AM", "--", "spotapi/sync/song.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not revision:
        return {
            "available": False,
            "reason": "Legacy source is absent from this checkout's history",
        }

    source = subprocess.run(
        ["git", "show", f"{revision}:spotapi/sync/song.py"],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    song = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == "Song"
    )
    method = next(
        node
        for node in song.body
        if isinstance(node, ast.FunctionDef) and node.name == "query_songs"
    )
    namespace: dict[str, Any] = {"json": json, "Mapping": Mapping, "Any": Any}

    exec(
        compile(ast.Module(body=[method], type_ignores=[]), "<v1 query_songs>", "exec"),
        namespace,
    )

    payload = {
        "data": {
            "searchV2": {
                "tracksV2": {
                    "items": [
                        {
                            "item": {
                                "data": {
                                    "id": "example",
                                    "name": "Example",
                                    "uri": "spotify:track:example",
                                }
                            }
                        }
                    ]
                }
            }
        }
    }
    calls = 0

    def post(*args: object, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1

        return SimpleNamespace(fail=False, response=payload)

    def part_hash(name: str) -> str:
        return "a" * 64

    instance = SimpleNamespace(
        base=SimpleNamespace(client=SimpleNamespace(post=post), part_hash=part_hash)
    )
    query_songs = cast(LegacySearch, namespace["query_songs"])
    times: list[float] = []

    for _ in range(20):
        start = time.perf_counter()

        for _ in range(1000):
            result = query_songs(instance, "Example", limit=1)

            assert (
                result["data"]["searchV2"]["tracksV2"]["items"][0]["item"]["data"]["name"]
                == "Example"
            )

        times.append((time.perf_counter() - start) / 1000)

    return {
        **summary(times),
        "source_revision": revision,
        "source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "logical_requests": calls,
        "scope": "Actual v1 query_songs builder, fake sync transport, raw response; no auth/discovery/network. "
        "The v2 warm measurements also include typed decoding and asyncio scheduling.",
    }


async def live(samples: int) -> dict[str, object]:
    calls = 0
    original = HTTPClient.request

    async def counted(
        self: HTTPClient,
        method: Methods,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        nonlocal calls
        calls += 1

        return await original(
            self, method, url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )

    async def search() -> None:
        result = await Public.search("Daft Punk", types="track", limit=5)

        assert result.tracks

    result: dict[str, object] = {}

    with patch.object(HTTPClient, "request", counted):
        cold: list[float] = []
        cold_counts: list[int] = []

        for _ in range(3):
            await close_query_clients()

            before = calls

            cold.append(await timed(search))
            cold_counts.append(calls - before)

        result["new_session_existing_disk_cache"] = {
            **summary(cold),
            "logical_http_calls": calls,
            "logical_http_calls_per_sample": cold_counts,
        }

        async with Catalogue() as catalogue:

            async def warm_search() -> None:
                result = await catalogue.search("Daft Punk", types="track", limit=5)

                assert result.tracks

            await warm_search()

            before = calls
            warm = [await timed(warm_search) for _ in range(samples)]
            result["warm_sequential"] = {
                **summary(warm),
                "logical_http_calls": calls - before,
            }
            before = calls

            elapsed = await timed(lambda: asyncio.gather(*(warm_search() for _ in range(samples))))

            result["concurrent"] = {
                "count": samples,
                "batch_ms": round(elapsed * 1000, 4),
                "logical_http_calls": calls - before,
            }

        await close_query_clients()

        with tempfile.TemporaryDirectory(prefix="spotapi-benchmark-") as directory:
            cache = QueryCache(Path(directory) / "queries.json")
            before = calls

            with patch("spotapi.session.QueryCache", return_value=cache):
                elapsed = await timed(lambda: Public.search("Daft Punk", types="track", limit=5))

                await close_query_clients()

            result["new_session_empty_disk_cache"] = {
                "samples_ms": [round(elapsed * 1000, 4)],
                "logical_http_calls": calls - before,
            }

    return result


async def main(args: Options) -> None:
    if args.samples < 1:
        raise ValueError("samples must be positive")

    result: dict[str, object] = {
        "python": platform.python_version(),
        "methodology": "perf_counter; offline fakes yield at creation and request; no artificial network delay. "
        "Live times include network, auth/discovery, parsing. Counts are logical HTTP calls, "
        "not wire attempts. Cold means a new session, with existing OS/disk caches.",
        "exclusive_pool_before": await offline_owner(False),
        "shared_client_after": await offline_owner(True),
        "decode": decode_benchmark(),
        "v1_query_builder": legacy_search_overhead(),
    }

    if args.live:
        result["live"] = await live(args.samples)

    encoded = json.dumps(result, indent=2)

    if args.output:
        Path(args.output).write_text(encoded + "\n", encoding="utf-8")

    print(encoded)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--samples", type=int, default=10)
    parser.add_argument("--output")
    asyncio.run(main(parser.parse_args(namespace=Options())))
