from __future__ import annotations

import asyncio
import base64
import json
import time
import uuid
from pathlib import Path
from typing import Any, ClassVar
from dataclasses import dataclass
from platformdirs import user_cache_dir

from spotapi.v2.client import AsyncClient
from spotapi.v2.types import HTTPError
from spotapi.v2.utils import (
    combine_chunks,
    extract_js_links,
    extract_mappings,
    extract_query_hashes,
    timed_cache,
)
from spotapi.v2.specialized.totp import build_totp

__all__: tuple[str, ...] = (
    "AccessToken",
    "AuthSession",
    "BundleSession",
    "ServerConfig",
    "fetch_js_bundles",
)


@timed_cache()
async def fetch_js_bundles(
    session: BundleSession | None = None,
) -> dict[str, str] | None:
    if session is None:
        async with AsyncClient() as client:
            session = BundleSession(client)

    try:
        return await session.load()
    except HTTPError:
        return


@dataclass(slots=True, frozen=True)
class ServerConfig:
    client_version: str
    build_version: str
    recaptcha_key: str
    correlation_id: str


@dataclass(slots=True, repr=True)
class AccessToken:
    client_id: str
    access_token: str
    expires_at_ms: int
    client_token: str | None = None

    @property
    def expires_in(self) -> float:
        """Seconds until expiry. Negative if already expired."""
        return self.expires_at_ms / 1000 - time.time()

    @property
    def is_expired(self) -> bool:
        return self.expires_in <= 0


class BundleSession:
    _BASE_URL: ClassVar[str] = "https://open.spotify.com/"
    _CDN_PREFIX: ClassVar[str] = "https://open.spotifycdn.com/cdn/build/web-player/"
    _APP_CONFIG_TAG: ClassVar[str] = '<script id="appServerConfig" type="text/plain">'
    _CACHE_FILENAME: ClassVar[str] = "queries.json"

    __slots__: tuple[str, ...] = (
        "_client",
        "_bundles",
        "_links",
        "_app_server_config",
        "_hashes",
    )

    def __init__(self, client: AsyncClient) -> None:
        self._client = client
        self._bundles: dict[str, str] = {}
        self._links: list[str] = []
        self._app_server_config: dict[str, Any] | None = None
        self._hashes: dict[str, str] | None = self._load_query_cache()

    def __repr__(self) -> str:
        return (
            f"<BundleSession"
            f" bundles={len(self._bundles)}"
            f" links={len(self._links)}"
            f" warmed={bool(self._bundles)}>"
        )

    @staticmethod
    def _resolve_cache_path(*, create: bool = False) -> Path | None:
        cache_dir = Path(user_cache_dir(appname="spotapi"))
        if not cache_dir.exists():
            if not create:
                return
            cache_dir.mkdir(parents=True, exist_ok=True)

        path = cache_dir / BundleSession._CACHE_FILENAME
        if not path.exists():
            if not create:
                return
            path.touch()

        return path

    @staticmethod
    def _load_query_cache() -> dict[str, str] | None:
        path = BundleSession._resolve_cache_path()
        if path is None:
            return

        try:
            with path.open() as fp:
                data = json.load(fp)
        except (json.JSONDecodeError, OSError, ValueError):
            return

        return data if isinstance(data, dict) else None  # type: ignore[return-value]

    def _save_query_cache(self) -> None:
        path = self._resolve_cache_path(create=True)
        if path is None:
            return

        try:
            with path.open("w") as fp:
                json.dump(self.all_queries, fp)
        except OSError:
            pass

    @property
    def server_config(self) -> ServerConfig:
        if self._app_server_config is None:
            raise RuntimeError(
                "server_config is unavailable until the initial request has been made"
            )

        cfg = self._app_server_config
        return ServerConfig(
            client_version=str(cfg["clientVersion"]),
            build_version=str(cfg["buildVersion"]),
            recaptcha_key=str(cfg["recaptchaWebPlayerFraudSiteKey"]),
            correlation_id=str(cfg["correlationId"]),
        )

    @property
    def bundles(self) -> dict[str, str]:
        return self._bundles

    @property
    def all_queries(self) -> dict[str, str]:
        if self._hashes is not None:
            return self._hashes

        if not self._bundles:
            raise RuntimeError(
                "all_queries is unavailable until BundleSession.warm() has been called"
            )

        hashes: dict[str, str] = {}
        for data in self._bundles.values():
            hashes.update(extract_query_hashes(data))

        self._hashes = hashes
        return hashes

    def query_hash(self, name: str, /) -> str:
        """Return the SHA-256 hash for *name*"""
        return self.all_queries.get(name, "")

    async def warm(self) -> None:
        if self._bundles:
            return

        if bundles := await fetch_js_bundles(self):
            self._bundles = bundles
            self._save_query_cache()

    async def load(self) -> dict[str, str]:
        if not self._links:
            await self._discover_links()

        all_fresh: dict[str, str] = {}

        for _ in range(2):
            unfetched = list(set(self._links) - self._bundles.keys())
            if not unfetched:
                break

            results: list[str | BaseException] = await asyncio.gather(
                *[self._fetch_bundle(url) for url in unfetched],
                return_exceptions=True,
            )
            fresh: dict[str, str] = {}
            for url, result in zip(unfetched, results):
                if isinstance(result, str):
                    fresh[url] = result

            self._bundles.update(fresh)
            all_fresh.update(fresh)

            embedded = self._extract_embedded_links(self._bundles)
            self._links = list(set(self._links) | set(embedded))

        return all_fresh

    async def _fetch_bundle(self, url: str) -> str:
        response = await self._client.get(url)
        return response.text

    async def _discover_links(self) -> None:
        response = await self._client.get(self._BASE_URL)
        html = response.text

        if self._APP_CONFIG_TAG not in html:
            raise ValueError("appServerConfig tag not found in Spotify HTML")

        raw_config = html.split(self._APP_CONFIG_TAG, 1)[1].split("</script>", 1)[0]
        self._app_server_config = json.loads(base64.b64decode(raw_config))
        self._links.extend(extract_js_links(html))

    @staticmethod
    def _extract_embedded_links(bundles: dict[str, str]) -> list[str]:
        web_player_src = next(
            (src for url, src in bundles.items() if "/web-player." in url),
            "",
        )
        hash_map, name_map = extract_mappings(web_player_src)
        return [BundleSession._CDN_PREFIX + chunk for chunk in combine_chunks(name_map, hash_map)]


class AuthSession:
    _TOKEN_URL: ClassVar[str] = "https://open.spotify.com/api/token"
    _CLIENT_TOKEN_URL: ClassVar[str] = "https://clienttoken.spotify.com/v1/clienttoken"
    _REFRESH_BUFFER: ClassVar[float] = 60.0

    __slots__: tuple[str, ...] = (
        "_token",
        "_refresh_task",
        "_device_id",
        "_raw_http_client",
        "client",
        "session",
    )

    def __init__(self, client: AsyncClient) -> None:
        self._token: AccessToken | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._device_id: str | None = None
        self._raw_http_client = client.protocols.http

        self.client = client
        self.session = BundleSession(client)

    def __repr__(self) -> str:
        refreshing = self._refresh_task is not None and not self._refresh_task.done()
        return f"<AuthSession" f" token={self._token!r}" f" auto_refresh={refreshing}>"

    @property
    def token(self) -> AccessToken:
        if self._token is None:
            raise RuntimeError("token is unavailable until authorize() has been awaited")
        return self._token

    async def authorize(self) -> AccessToken:
        await self.session.warm()

        cookie = self._raw_http_client.get_cookie("sp_t")
        self._device_id = cookie if cookie is not None else str(uuid.uuid4())

        self._token = await self._fetch_access_token()
        self._token.client_token = await self._fetch_client_token()

        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(
                self._auto_refresh(), name="spotify-token-refresh"
            )

        return self.token

    async def close(self) -> None:
        if self._refresh_task is not None and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass

        await self.client.close()

    async def _fetch_access_token(self) -> AccessToken:
        version, totp = build_totp(self.session.bundles)
        response = await self.client.get(
            self._TOKEN_URL,
            query={
                "reason": "init",
                "productType": "web-player",
                "totp": totp,
                "totpServer": totp,
                "totpVer": version,
            },
        )

        if not response.json:
            raise ValueError("Token endpoint returned an empty response body")

        return AccessToken(
            client_id=response.json.clientId,
            access_token=response.json.accessToken,
            expires_at_ms=response.json.accessTokenExpirationTimestampMs,
        )

    async def _fetch_client_token(self) -> str:
        cfg = self.session.server_config
        payload: dict[str, Any] = {
            "client_data": {
                "client_version": cfg.client_version,
                "client_id": self.token.client_id,
                "js_sdk_data": {
                    "device_brand": "unknown",
                    "device_model": "unknown",
                    "os": "windows",
                    "os_version": "NT 10.0",  # todo: make dynamic
                    "device_id": self._device_id,
                    "device_type": "computer",
                },
            }
        }
        response = await self.client.post(
            self._CLIENT_TOKEN_URL,
            json=payload,
            headers={
                "accept": "application/json",
                "content-type": "application/json",
            },
        )

        if not response.json:
            raise ValueError("Client token endpoint returned an empty response body")

        return str(response.json.granted_token.token)

    async def _auto_refresh(self) -> None:
        while True:
            if self._token is not None:
                delay = max(0.0, self._token.expires_in - self._REFRESH_BUFFER)
                await asyncio.sleep(delay)

            self._token = await self._fetch_access_token()
            self._token.client_token = await self._fetch_client_token()
