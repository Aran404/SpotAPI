"""Manage Spotify web-player configuration, query hashes, and authentication.

This module provides a best-effort cache for persisted GraphQL queries and an
asynchronous authentication session with automatic token renewal.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import sys
import time
import uuid
from collections.abc import Iterable, Mapping
from contextlib import suppress
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Final, Self, TypedDict, cast

from ._protocol.bundles import (
    combine_chunks,
    extract_js_links,
    extract_mappings,
    extract_query_hashes,
)
from ._protocol.routes import CLIENT_TOKEN, TOKEN
from ._protocol.totp import build_totp
from .client import AsyncClient
from .types import HTTPError

__all__ = (
    "AccessToken",
    "AuthSession",
    "BundleSession",
    "QueryCache",
    "ServerConfig",
    "fetch_js_bundles",
)

_APP_NAME: Final[str] = "spotapi"
_CACHE_FILENAME: Final[str] = "queries.json"
_logger = logging.getLogger(__name__)

_BASE_URL: Final[str] = "https://open.spotify.com/"
_CDN_PREFIX: Final[str] = "https://open.spotifycdn.com/cdn/build/web-player/"
_APP_CONFIG_TAG: Final[str] = '<script id="appServerConfig" type="text/plain">'
_DISCOVERY_PASSES: Final[int] = 3
_MAX_BUNDLE_DOWNLOADS: Final[int] = 8

_TOKEN_URL: Final[str] = TOKEN
_CLIENT_TOKEN_URL: Final[str] = CLIENT_TOKEN
_REFRESH_BUFFER: Final[float] = 60.0
_MIN_REFRESH_DELAY: Final[float] = 1.0
_RETRY_DELAY: Final[float] = 5.0


def normalize_language(value: str) -> str:
    """Normalize a language or locale into a bounded Accept-Language value."""
    value = value.replace("_", "-")
    if len(value) > 64 or not re.fullmatch(r"[A-Za-z]{2,3}(?:-[A-Za-z0-9]{1,8})*", value):
        raise ValueError("Use a language code such as en, en-US or fr-CA")
    return value


def _user_cache_dir(app: str) -> Path:
    """Return the platform-appropriate user cache directory for ``app``."""
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local"

        return Path(base) / app / "Cache"

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / app

    xdg = os.environ.get("XDG_CACHE_HOME", "")
    base = Path(xdg) if xdg and Path(xdg).is_absolute() else Path.home() / ".cache"

    return base / app


def _parse_cookie_header(header: str) -> list[Mapping[str, Any]]:
    """Convert a Cookie header into the cookie mappings accepted by the client."""
    pairs = (part.strip().partition("=") for part in header.split(";"))

    return [{"name": name, "value": value} for name, sep, value in pairs if sep]


class _AppServerConfig(TypedDict):
    """Fields consumed from Spotify's app-server configuration payload."""

    clientVersion: str
    buildVersion: str
    recaptchaWebPlayerFraudSiteKey: str
    correlationId: str


def _decode_app_server_config(encoded: str) -> _AppServerConfig:
    """Decode Spotify's base64 JSON configuration into typed fields."""
    data: object = json.loads(base64.b64decode(encoded))

    if not isinstance(data, dict):
        raise ValueError("appServerConfig must contain a JSON object")

    config = cast("dict[str, object]", data)
    keys = (
        "clientVersion",
        "buildVersion",
        "recaptchaWebPlayerFraudSiteKey",
        "correlationId",
    )
    values = {key: config.get(key) for key in keys}

    if any(not isinstance(value, str) for value in values.values()):
        raise ValueError(
            "appServerConfig is missing a required field or contains a non-string value"
        )

    return cast(_AppServerConfig, values)


@dataclass(slots=True, frozen=True)
class ServerConfig:
    """Normalized Spotify web-player configuration.

    Attributes:
        client_version: Version advertised by the web player.
        build_version: Identifier of the current web-player build.
        recaptcha_key: Public reCAPTCHA site key supplied by Spotify.
        correlation_id: Correlation identifier for the configuration response.
    """

    client_version: str
    build_version: str
    recaptcha_key: str
    correlation_id: str

    @classmethod
    def from_raw(cls, raw: _AppServerConfig) -> Self:
        """Create a configuration from Spotify's camel-case field names.

        Args:
            raw: App-server configuration from the web-player HTML.

        Returns:
            A normalized, immutable configuration instance.

        Raises:
            KeyError: If a required configuration field is missing.
        """
        return cls(
            client_version=str(raw["clientVersion"]),
            build_version=str(raw["buildVersion"]),
            recaptcha_key=str(raw["recaptchaWebPlayerFraudSiteKey"]),
            correlation_id=str(raw["correlationId"]),
        )


@dataclass(slots=True, frozen=True)
class AccessToken:
    """An access token and its associated client credentials.

    Secret token values are excluded from the generated representation.

    Attributes:
        client_id: Client identifier associated with the access token.
        access_token: Bearer token used to authenticate requests.
        expires_at_ms: Expiration time in Unix epoch milliseconds.
        client_token: Optional token required by web-player requests.
    """

    client_id: str
    access_token: str = field(repr=False)
    expires_at_ms: int
    client_token: str | None = field(default=None, repr=False)
    is_anonymous: bool | None = None

    @property
    def expires_in(self) -> float:
        """Return seconds remaining before expiry; negative once expired."""
        return self.expires_at_ms / 1000 - time.time()

    @property
    def is_expired(self) -> bool:
        """Return whether the access token has reached its expiry time."""
        return self.expires_in <= 0


class QueryCache:
    """Store persisted-query hashes in a best-effort on-disk JSON cache.

    Unreadable or invalid cache contents are treated as cache misses. Failed
    writes do not interrupt the caller because caching is optional.

    Attributes:
        path: Location of the JSON cache file.
    """

    __slots__ = ("path",)

    def __init__(self, path: Path | None = None) -> None:
        """Initialize the cache.

        Args:
            path: Override for the default per-user cache location.
        """
        self.path = path if path is not None else _user_cache_dir(_APP_NAME) / _CACHE_FILENAME

    def load(self, build_version: str | None = None) -> dict[str, str] | None:
        """Load validated query hashes from disk.

        Returns:
            A nonempty mapping of query names to hashes, or ``None`` if the
            file is absent, unreadable, empty, or invalid.
        """
        try:
            if time.time() - self.path.stat().st_mtime > 86400:
                return None

            # Query metadata should remain small, even for malformed caches.
            with self.path.open(encoding="utf-8") as cache_file:
                source = cache_file.read(1_048_577)

            if len(source) > 1_048_576:
                return None

            data: object = json.loads(source)
        except (OSError, ValueError):
            return None

        if not isinstance(data, dict) or not data:
            return None

        envelope = cast(dict[object, object], data)

        if envelope.get("format") != 2:
            return None

        if build_version is not None and envelope.get("build") != build_version:
            return None

        hashes = envelope.get("hashes")

        if not isinstance(hashes, dict) or not hashes:
            return None

        raw = cast(dict[object, object], hashes)

        if len(raw) > 8192:
            return None

        result: dict[str, str] = {}

        for key, value in raw.items():
            if not isinstance(key, str) or not isinstance(value, str):
                return None

            if (
                not key
                or len(key) > 256
                or len(value) != 64
                or any(c not in "0123456789abcdef" for c in value)
            ):
                return None

            result[key] = value

        return result

    def save(self, hashes: Mapping[str, str], *, build_version: str = "") -> None:
        """Atomically replace the cache file when the filesystem permits it.

        Each write uses a unique temporary path so concurrent sessions cannot
        overwrite one another's in-progress temporary files. Any I/O error
        is intentionally ignored; fetching hashes must not depend on caching.

        Args:
            hashes: Query-name-to-hash mapping to serialize as JSON.
        """
        temporary = self.path.with_name(f"{self.path.name}.{uuid.uuid4().hex}.tmp")

        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary.write_text(
                json.dumps({"format": 2, "build": build_version, "hashes": dict(hashes)}),
                encoding="utf-8",
            )
            temporary.replace(self.path)
        except OSError:
            pass
        finally:
            # Failed writes must not leave a partially written cache behind.
            with suppress(OSError):
                temporary.unlink(missing_ok=True)


class BundleSession:
    """Discover, fetch, and cache Spotify's persisted GraphQL query hashes.

    Args:
        client: HTTP client used for HTML and JavaScript requests.
        cache: Optional custom cache; a per-user cache is used by default.

    Note:
        The ``bundles`` and ``all_queries`` properties expose live mappings.
        Mutating them modifies this session's in-memory state.
    """

    __slots__ = (
        "_client",
        "_cache",
        "_bundles",
        "_links",
        "_app_server_config",
        "_hashes",
        "_hashes_loaded",
    )

    def __init__(self, client: AsyncClient, *, cache: QueryCache | None = None) -> None:
        """Borrow an HTTP client and configure discovery of public web-player bundles."""
        self._client = client
        self._cache = cache if cache is not None else QueryCache()
        self._bundles: dict[str, str] = {}
        self._links: set[str] = set()
        self._app_server_config: _AppServerConfig | None = None
        self._hashes: dict[str, str] | None = None
        self._hashes_loaded = False

    def __repr__(self) -> str:
        return (
            f"<{type(self).__name__} "
            f"bundles={len(self._bundles)} links={len(self._links)} "
            f"warmed={bool(self._bundles)}>"
        )

    @property
    def server_config(self) -> ServerConfig:
        """Return the configuration discovered from Spotify's HTML.

        Raises:
            RuntimeError: If the initial HTML request has not completed.
        """
        if self._app_server_config is None:
            raise RuntimeError(
                "server_config is unavailable until the initial request has been made"
            )

        return ServerConfig.from_raw(self._app_server_config)

    @property
    def bundles(self) -> dict[str, str]:
        """Return the live mapping of JavaScript URLs to their source text."""
        return self._bundles

    @property
    def all_queries(self) -> dict[str, str]:
        """Return hashes already loaded or discovered from local bundles.

        Call :meth:`warm` first to include disk-cached hashes.

        Raises:
            RuntimeError: If neither hashes nor bundles are available.
        """
        if self._hashes is None:
            if not self._bundles:
                raise RuntimeError(
                    "all_queries is unavailable until BundleSession.warm() has been called"
                )

            self._hashes = self._collect_hashes()

        return self._hashes

    def query_hash(self, name: str, /) -> str:
        """Find a persisted-query hash by name.

        Args:
            name: GraphQL operation name.

        Returns:
            The hash, or an empty string when the name is unknown.

        Raises:
            RuntimeError: If no query hashes or bundles are available yet.
        """
        return self.all_queries.get(name, "")

    async def warm(self) -> None:
        """Fetch missing bundles and refresh persisted-query hashes.

        Existing bundles, including those retrieved by a prior ``load()``
        call, are used to refresh a potentially stale disk cache. If no hashes
        can be extracted, the existing cached hashes remain available.
        """
        if self._app_server_config is None:
            await self._discover_links()

        if not self._hashes_loaded:
            cached = await asyncio.to_thread(self._cache.load, self.server_config.build_version)

            if cached:
                self._hashes = {**cached, **(self._hashes or {})}

            self._hashes_loaded = True

        if not self._bundles:
            if self._hashes:
                # The current main bundle contains the TOTP material. Cached
                # hashes for this exact build avoid downloading every chunk.
                primary = {url for url in self._links if "/web-player." in url}

                self._bundles.update(await self._fetch_all(primary))

            if not self._bundles:
                await fetch_js_bundles(self)

        if not self._bundles:
            return

        # Merge with cached entries: a partial bundle download must not
        # discard valid hashes that were already discovered earlier.
        hashes = await asyncio.to_thread(self._collect_hashes)

        if hashes:
            combined = {**(self._hashes or {}), **hashes}

            if combined != self._hashes:
                self._hashes = combined

                await asyncio.to_thread(
                    self._cache.save,
                    combined,
                    build_version=self.server_config.build_version,
                )

        # Only the main bundle is needed for token renewal. Explicit load()
        # remains available to callers who want the complete source set.
        primary = {url: source for url, source in self._bundles.items() if "/web-player." in url}

        if primary:
            self._bundles.clear()
            self._bundles.update(primary)

    async def load(self) -> dict[str, str]:
        """Discover and fetch JavaScript bundles over a bounded number of passes.

        The first pass fetches links found in HTML. Subsequent passes can
        follow chunk references embedded in previously fetched bundles.
        Individual bundle download errors are ignored by ``_fetch_all``.

        Returns:
            Bundles newly fetched by this call, keyed by URL.

        Raises:
            ValueError: If the expected app-server configuration tag is absent.
        """
        if not self._links:
            await self._discover_links()

        fetched: dict[str, str] = {}
        attempted: set[str] = set()

        for _ in range(_DISCOVERY_PASSES):
            pending = self._links - self._bundles.keys() - attempted

            if not pending:
                break

            attempted.update(pending)

            fresh = await self._fetch_all(pending)

            self._bundles.update(fresh)
            fetched.update(fresh)

            self._links |= await asyncio.to_thread(self._embedded_links, self._bundles)

        return fetched

    def _collect_hashes(self) -> dict[str, str]:
        """Extract persisted-query hashes from all available bundles."""
        hashes: dict[str, str] = {}

        for source in self._bundles.values():
            hashes.update(extract_query_hashes(source))

        return hashes

    async def _fetch_all(self, urls: Iterable[str]) -> dict[str, str]:
        """Fetch bundles in small concurrent batches; failed downloads are skipped."""
        targets = list(urls)
        fetched: dict[str, str] = {}

        async def fetch(url: str) -> str | None:
            """Fetch runtime authentication metadata from Spotify's deployed resources."""
            try:
                return await self._fetch_bundle(url)
            except asyncio.CancelledError:
                raise
            except Exception:
                _logger.debug("Skipping unavailable Spotify bundle %s", url, exc_info=True)

                return None

        for start in range(0, len(targets), _MAX_BUNDLE_DOWNLOADS):
            batch = targets[start : start + _MAX_BUNDLE_DOWNLOADS]

            async with asyncio.TaskGroup() as task_group:
                tasks = {
                    url: task_group.create_task(fetch(url), name="spotify-bundle-fetch")
                    for url in batch
                }

            fetched.update(
                (url, result)
                for url, task in tasks.items()
                if (result := task.result()) is not None
            )

        return fetched

    async def _fetch_bundle(self, url: str) -> str:
        """Download one JavaScript bundle as text."""
        response = await self._client.get(url)

        return response.text

    async def _discover_links(self) -> None:
        """Read the app configuration and JavaScript links from Spotify HTML."""
        response = await self._client.get(_BASE_URL)

        html = response.text

        _, tag, rest = html.partition(_APP_CONFIG_TAG)

        if not tag:
            raise ValueError("appServerConfig tag not found in Spotify HTML")

        raw_config = rest.partition("</script>")[0]
        self._app_server_config = _decode_app_server_config(raw_config)

        self._links.update(url for url in extract_js_links(html) if url.startswith(_CDN_PREFIX))

    @staticmethod
    def _embedded_links(bundles: Mapping[str, str]) -> set[str]:
        """Find chunk URLs referenced by the main web-player bundle."""
        web_player_src = next(
            (src for url, src in bundles.items() if "/web-player." in url),
            "",
        )

        if not web_player_src:
            return set()

        try:
            hash_map, name_map = extract_mappings(web_player_src)
        except ValueError:
            return set()

        name_map = {key: name_map.get(key, str(key)) for key in hash_map}

        return {_CDN_PREFIX + chunk for chunk in combine_chunks(name_map, hash_map)}


async def fetch_js_bundles(
    session: BundleSession | None = None,
) -> dict[str, str] | None:
    """Fetch Spotify JavaScript bundles using an existing or temporary client.

    Args:
        session: Existing bundle session. A temporary client is created and
            closed when no session is supplied.

    Returns:
        Newly fetched bundles, or ``None`` if an ``HTTPError`` occurs.
    """
    if session is not None:
        return await _try_load(session)

    async with AsyncClient() as client:
        return await _try_load(BundleSession(client))


async def _try_load(session: BundleSession) -> dict[str, str] | None:
    """Load bundles, treating HTTP errors as a best-effort cache miss."""
    try:
        return await session.load()
    except HTTPError:
        return None


def _observe_refresh(task: asyncio.Task[None]) -> None:
    """Retrieve refresh-task failures for explicit logging and shutdown."""
    if not task.cancelled() and (error := task.exception()) is not None:
        _logger.error("Token refresh stopped unexpectedly", exc_info=error)


class AuthSession:
    """Manage Spotify web-player credentials and automatic token renewal.

    Args:
        client: HTTP client owned by the session and closed by ``close()``.

    Note:
        Entering the async context does not call ``authorize()``. Use
        ``from_cookies()`` or explicitly await ``authorize()`` first.
    """

    __slots__ = (
        "_token",
        "_refresh_task",
        "_device_id",
        "_auth_lock",
        "_language",
        "_require_user",
        "_raw_http_client",
        "client",
        "session",
    )

    def __init__(self, client: AsyncClient, *, language: str = "en") -> None:
        """Own the supplied client's lifetime and prepare authorization and token refresh."""
        self._token: AccessToken | None = None
        self._refresh_task: asyncio.Task[None] | None = None
        self._device_id: str | None = None
        self._auth_lock = asyncio.Lock()
        self.language = language
        self._require_user = False
        self._raw_http_client = client.transport

        self.client = client
        self.session = BundleSession(client)
        client.session = self

    def __repr__(self) -> str:
        refreshing = self._refresh_task is not None and not self._refresh_task.done()

        return f"<{type(self).__name__} token={self._token!r} auto_refresh={refreshing}>"

    async def __aenter__(self) -> Self:
        """Enter this resource's asynchronous ownership scope."""
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        """Release resources owned by this asynchronous scope."""
        try:
            await self.close()
        except Exception as exc:
            if len(exc_info) >= 2 and isinstance(exc_info[1], asyncio.CancelledError):
                raise exc_info[1] from exc

            raise

    @classmethod
    async def from_cookies(
        cls,
        cookies: list[Mapping[str, Any]] | str,
        proxy: str | None = None,
        *,
        client: AsyncClient | None = None,
        language: str = "en",
    ) -> Self:
        """Create and authorize a session from Spotify web cookies.

        Args:
            cookies: A Cookie header or client-compatible cookie mappings.
            proxy: Optional HTTP proxy URL passed to the client factory.

        Returns:
            An authorized session responsible for its HTTP client.

        Raises:
            HTTPError: If token retrieval fails with an HTTP error.
            ValueError: If a required token response is empty.

        Note:
            The client is closed if authorization fails or is cancelled.
        """
        language = normalize_language(language)
        if isinstance(cookies, str):
            cookies = _parse_cookie_header(cookies)

        if not any(cookie.get("name") == "sp_dc" and cookie.get("value") for cookie in cookies):
            raise ValueError("A nonempty sp_dc cookie is required")

        if client is not None and proxy is not None:
            raise ValueError("Configure a proxy on the supplied client")

        if client is None:
            client = await AsyncClient.new(proxy=proxy)

        session = cls(client, language=language)
        session._require_user = True
        authorized = False

        try:
            client.transport.set_cookies(cookies)

            token = await session.authorize()
            if token.is_anonymous is True:
                raise HTTPError(
                    "Spotify rejected the cookie session and returned guest credentials",
                    status_code=401,
                )

            authorized = True
        finally:
            # Cleanup must run even when authorization is cancelled.
            if not authorized:
                await session.close()

        return session

    @property
    def token(self) -> AccessToken:
        """Return the current token, or raise if not yet authorized.

        Raises:
            RuntimeError: If ``authorize()`` has not completed successfully.
        """
        if self._token is None:
            raise RuntimeError("token is unavailable until authorize() has been awaited")

        return self._token

    @property
    def authorized_headers(self) -> dict[str, str]:
        """Construct the headers required for authenticated requests.

        Raises:
            RuntimeError: If the token, client token, or server
                configuration is unavailable.
        """
        token = self.token

        if not token.client_token:
            raise RuntimeError("Client token not set for authorized headers")

        return {
            "authorization": f"Bearer {token.access_token}",
            "client-token": token.client_token,
            "spotify-app-version": self.session.server_config.client_version,
            "app-platform": "WebPlayer",
            "origin": "https://open.spotify.com",
            "referer": "https://open.spotify.com/",
            "accept-language": self.language,
        }

    @property
    def language(self) -> str:
        """Read or replace the validated language used by authorized requests."""
        return self._language

    @language.setter
    def language(self, value: str) -> None:
        """Read or replace the validated language used by authorized requests."""
        self._language = normalize_language(value)

    async def authorize(self) -> AccessToken:
        """Obtain credentials and start automatic renewal if needed.

        Returns:
            The newly issued access token with its client token.
        """
        async with self._auth_lock:
            await self.session.warm()
            self._device_id = self._raw_http_client.get_cookie("sp_t") or str(uuid.uuid4())
            return await self._renew()

    async def refresh(self, *, previous_token: str | None = None) -> AccessToken:
        """Renew once when concurrent callers reject the same credentials."""
        async with self._auth_lock:
            if (
                previous_token is not None
                and self._token is not None
                and self._token.access_token != previous_token
            ):
                return self._token
            return await self._renew()

    async def _renew(self) -> AccessToken:
        """Replace tokens under the authentication lock without accepting a guest downgrade."""
        token = await self._issue_token()
        if self._require_user and token.is_anonymous is True:
            raise HTTPError(
                "Spotify rejected the cookie session and returned guest credentials",
                status_code=401,
            )
        self._token = token
        if self._refresh_task is None or self._refresh_task.done():
            self._refresh_task = asyncio.create_task(
                self._auto_refresh(), name="spotify-token-refresh"
            )

            self._refresh_task.add_done_callback(_observe_refresh)

        return self._token

    async def close(self) -> None:
        """Stop token renewal and close the underlying client."""
        try:
            await self.stop_refresh()
        finally:
            await self.client.close()

    async def stop_refresh(self) -> None:
        """Stop token renewal without closing the client's transports."""
        task, self._refresh_task = self._refresh_task, None

        if task is not None:
            if not task.done():
                task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                # Ignore the refresh task's cancellation, not our caller's.
                current = asyncio.current_task()

                if current is not None and current.cancelling():
                    raise
            except Exception:
                _logger.exception("Token refresh task failed before session shutdown")

    async def _issue_token(self) -> AccessToken:
        """Retrieve the access token and its companion client token."""
        access = await self._fetch_access_token()

        client_token = await self._fetch_client_token(access.client_id)

        return replace(access, client_token=client_token)

    async def _fetch_access_token(self) -> AccessToken:
        """Request a web-player access token using the current TOTP."""
        version, totp = await asyncio.to_thread(build_totp, self.session.bundles)

        response = await self.client.get(
            _TOKEN_URL,
            query={
                "reason": "init",
                "productType": "web-player",
                "totp": totp,
                "totpServer": totp,
                "totpVer": version,
            },
        )

        body = response.json

        if body is None:
            raise ValueError("Token endpoint returned no JSON object")

        client_id: object = body.get("clientId")
        access_token: object = body.get("accessToken")
        expiry: object = body.get("accessTokenExpirationTimestampMs")

        if (
            not isinstance(client_id, str)
            or not isinstance(access_token, str)
            or type(expiry) is not int
        ):
            raise ValueError("Token endpoint returned invalid credentials")

        anonymous = body.get("isAnonymous")
        return AccessToken(
            client_id,
            access_token,
            expiry,
            is_anonymous=anonymous if isinstance(anonymous, bool) else None,
        )

    async def _fetch_client_token(self, client_id: str) -> str:
        """Request the client token associated with ``client_id``."""
        payload: dict[str, object] = {
            "client_data": {
                "client_version": self.session.server_config.client_version,
                "client_id": client_id,
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
            _CLIENT_TOKEN_URL,
            json=payload,
            headers={"accept": "application/json", "content-type": "application/json"},
            retry_safe=True,
        )

        body = response.json
        granted: object = body.get("granted_token") if body is not None else None

        if not isinstance(granted, dict):
            raise ValueError("Client token endpoint returned no granted_token object")

        token: object = cast(Mapping[str, object], granted).get("token")

        if not isinstance(token, str) or not token:
            raise ValueError("Client token endpoint returned an invalid token")

        return token

    async def _auto_refresh(self) -> None:
        """Refresh credentials before expiry and retry transient failures."""
        while True:
            token = self.token
            delay = token.expires_in - _REFRESH_BUFFER

            await asyncio.sleep(max(delay, _MIN_REFRESH_DELAY))

            try:
                await self.refresh(previous_token=token.access_token)
            except HTTPError as error:
                if (
                    error.status_code is not None
                    and 400 <= error.status_code < 500
                    and error.status_code not in {408, 425, 429}
                ):
                    raise
                await asyncio.sleep(_RETRY_DELAY)
