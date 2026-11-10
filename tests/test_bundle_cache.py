"""Build-aware discovery must reuse valid hashes and reject another build."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

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


async def test_valid_build_fetches_only_main_bundle(tmp_path: Path) -> None:
    cache = QueryCache(tmp_path / "queries.json")

    cache.save({"searchDesktop": "a" * 64}, build_version="current")

    session = Session(cache)

    await session.warm()

    assert session.downloads == ["https://cdn.test/web-player.main.js"]
    assert session.query_hash("searchDesktop") == "a" * 64


async def test_changed_build_rediscovers_hashes(tmp_path: Path) -> None:
    cache = QueryCache(tmp_path / "queries.json")

    cache.save({"obsoleteQuery": "b" * 64}, build_version="old")

    session = Session(cache)

    await session.warm()

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
