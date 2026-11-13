"""Build-aware discovery must reuse valid hashes and reject another build."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import Mock

import pytest

from spotapi import AsyncClient
from spotapi.session import BundleSession, QueryCache


class Session(BundleSession):
    def __init__(self, cache: QueryCache, build: str = "current") -> None:
        super().__init__(Mock(spec=AsyncClient), cache=cache)

        self.build = build
        self.downloads: list[str] = []

    async def _discover_links(self) -> None:
        self._app_server_config = {
            "clientVersion": "version",
            "buildVersion": self.build,
            "recaptchaWebPlayerFraudSiteKey": "",
            "correlationId": "",
        }
        self._links = {
            "https://cdn.test/web-player.main.js",
            "https://cdn.test/extra.js",
        }

    async def _fetch_bundle(self, url: str) -> str:
        self.downloads.append(url)

        if url.endswith("extra.js"):
            return '"searchDesktop", "query", "' + "a" * 64 + '"'

        return "main bundle"


async def test_bundle_workers_continue_while_one_download_is_slow(tmp_path: Path) -> None:
    release = asyncio.Event()
    progressed = asyncio.Event()
    active = 0
    peak = 0

    class Slow(Session):
        async def _fetch_bundle(self, url: str) -> str:
            nonlocal active, peak
            active += 1
            peak = max(peak, active)
            try:
                if url == "0":
                    await release.wait()
                else:
                    await asyncio.sleep(0)
                if url == "8":
                    progressed.set()
                return url
            finally:
                active -= 1

    session = Slow(QueryCache(tmp_path / "queries.json"))
    async with asyncio.TaskGroup() as group:
        task = group.create_task(session._fetch_all(map(str, range(20))))
        try:
            async with asyncio.timeout(2):
                await progressed.wait()
        finally:
            release.set()
    assert task.result() == {str(index): str(index) for index in range(20)}
    assert peak == 8
    assert active == 0


async def test_cancelled_discovery_waits_for_every_worker_to_stop(tmp_path: Path) -> None:
    started = asyncio.Event()
    blocked = asyncio.Event()
    active = 0

    class Blocked(Session):
        async def _fetch_bundle(self, url: str) -> str:
            nonlocal active
            active += 1
            if active == 8:
                started.set()
            try:
                await blocked.wait()
                return url
            finally:
                active -= 1

    session = Blocked(QueryCache(tmp_path / "queries.json"))
    task = asyncio.create_task(session._fetch_all(map(str, range(20))))
    try:
        async with asyncio.timeout(2):
            await started.wait()
    finally:
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert active == 0


async def test_valid_build_fetches_only_main_bundle(tmp_path: Path) -> None:
    cache = QueryCache(tmp_path / "queries.json")

    cache.save({"searchDesktop": "a" * 64}, build_version="current")

    session = Session(cache)

    await session.warm()

    assert session.downloads == ["https://cdn.test/web-player.main.js"]
    assert session.query_hash("searchDesktop") == "a" * 64


async def test_cold_search_fetches_entry_bundles_without_unrelated_routes(tmp_path: Path) -> None:
    route = "https://cdn.test/xpui-routes-search.current.js"

    class SearchSession(Session):
        async def _discover_links(self) -> None:
            await super()._discover_links()
            self._links.add(route)

        async def _fetch_bundle(self, url: str) -> str:
            if url == route:
                self.downloads.append(url)
                return '"searchDesktop", "query", "' + "a" * 64 + '"'
            return await super()._fetch_bundle(url)

    session = SearchSession(QueryCache(tmp_path / "queries.json"))
    await session.warm()
    assert set(session.downloads) == {route, "https://cdn.test/web-player.main.js"}
    assert await session.resolve_query("searchDesktop") == "a" * 64
    assert len(session.downloads) == 2


async def test_missing_queries_share_one_discovery_pass(tmp_path: Path) -> None:
    session = Session(QueryCache(tmp_path / "queries.json"))
    await session.warm()
    assert await asyncio.gather(
        session.resolve_query("searchDesktop"), session.resolve_query("searchDesktop")
    ) == ["a" * 64, "a" * 64]
    assert session.downloads.count("https://cdn.test/extra.js") == 1
    before = list(session.downloads)
    assert await session.resolve_query("removedQuery") == ""
    assert await session.resolve_query("removedQuery") == ""
    assert session.downloads == before


async def test_failed_route_download_does_not_become_a_permanent_query_miss(
    tmp_path: Path,
) -> None:
    class Flaky(Session):
        failed = False

        async def _fetch_bundle(self, url: str) -> str:
            if url.endswith("extra.js") and not self.failed:
                self.failed = True
                raise OSError("Temporary CDN failure")
            return await super()._fetch_bundle(url)

    session = Flaky(QueryCache(tmp_path / "queries.json"))
    await session.warm()
    assert await session.resolve_query("searchDesktop") == ""
    assert await session.resolve_query("searchDesktop") == "a" * 64


async def test_changed_build_rediscovers_hashes(tmp_path: Path) -> None:
    cache = QueryCache(tmp_path / "queries.json")

    cache.save({"obsoleteQuery": "b" * 64}, build_version="old")

    session = Session(cache)

    await session.warm()

    assert session.downloads == ["https://cdn.test/web-player.main.js"]
    assert await session.resolve_query("searchDesktop") == "a" * 64
    assert set(session.downloads) == session._links
    assert session.query_hash("obsoleteQuery") == ""
    assert cache.load("current") == {"searchDesktop": "a" * 64}
    assert cache.load("old") is None
    assert list(session.bundles) == ["https://cdn.test/web-player.main.js"]


async def test_failed_main_download_falls_back_to_discovery(tmp_path: Path) -> None:
    cache = QueryCache(tmp_path / "queries.json")

    cache.save({"searchDesktop": "a" * 64}, build_version="current")

    class Flaky(Session):
        async def _fetch_bundle(self, url: str) -> str:
            if not self.downloads:
                self.downloads.append(url)

                raise OSError("temporary failure")

            return await super()._fetch_bundle(url)

    session = Flaky(cache)

    await session.warm()

    assert "https://cdn.test/extra.js" in session.downloads
    assert session.query_hash("searchDesktop") == "a" * 64
