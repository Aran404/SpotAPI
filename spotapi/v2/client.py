"""Asynchronous HTTP and WebSocket client with validated HTTP responses."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Any, NamedTuple, Self, Unpack

import wreq

from .connection import HTTPClient, Response, WebSocketClient
from .connection.types import Methods
from .types import DefaultLogger, HTTPError

if TYPE_CHECKING:
    from wreq import ClientConfig

    from .connection import RateLimiter
    from .connection.types import BackoffStrategy, JitterStrategy
    from .session import AuthSession
    from .types import LoggerProtocol

    class _AsyncClientOptions(ClientConfig, total=False):
        backoff: BackoffStrategy
        jitter: JitterStrategy
        max_attempts: int
        max_delay: float
        rate_limiter: RateLimiter | None
        logger: LoggerProtocol

else:
    _AsyncClientOptions = Any

__all__ = ("AsyncClient",)


class _RawClients(NamedTuple):
    """The HTTP and WebSocket transports owned by an open client."""

    http: HTTPClient
    ws: WebSocketClient


async def _close_transports(
    http: HTTPClient | None,
    websocket: WebSocketClient | None,
) -> None:
    """Close owned transports and report all ordinary shutdown failures."""
    errors: list[Exception] = []

    try:
        if websocket is not None:
            await websocket.close()
    except Exception as exc:
        errors.append(exc)
    finally:
        if http is not None:
            try:
                await http.close()
            except Exception as exc:
                errors.append(exc)

    if len(errors) == 1:
        raise errors[0]

    if errors:
        raise ExceptionGroup("AsyncClient shutdown failed", errors)


def _observe_shutdown(task: asyncio.Task[None]) -> None:
    """Retrieve background shutdown failures to avoid unhandled task warnings."""
    if not task.cancelled() and (error := task.exception()) is not None:
        logging.getLogger(__name__).error("AsyncClient shutdown failed", exc_info=error)


class AsyncClient:
    """Manage reusable HTTP and WebSocket transports.

    Use :meth:`new` or ``async with`` to open the client, and :meth:`close`
    to release its transports. HTTP request methods require an open client
    and return validated successful responses.
    """

    __slots__ = ("_http", "_ws", "_proxy", "_close_task", "_session")

    def __init__(self, *, proxy: str | None = None) -> None:
        """Create an unopened client.

        Args:
            proxy: Optional proxy URL for the underlying HTTP transport.
        """
        self._session: AuthSession | None = None
        self._proxy = proxy
        self._http: HTTPClient | None = None
        self._ws: WebSocketClient | None = None
        self._close_task: asyncio.Task[None] | None = None

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<AsyncClient open={self._http is not None} proxy={self._proxy is not None}>"

    @property
    def protocols(self) -> _RawClients:
        """Return the underlying HTTP and WebSocket transports.

        Returns:
            A named tuple containing the open transports.

        Raises:
            RuntimeError: If the client is not open.
        """
        if self._http is None or self._ws is None:
            raise RuntimeError("Client is not open")

        return _RawClients(self._http, self._ws)

    @classmethod
    async def new(cls, *, proxy: str | None = None, **kwargs: Unpack[_AsyncClientOptions]) -> Self:
        """Create and open a client.

        Args:
            proxy: Optional proxy URL for the underlying HTTP transport.
            **kwargs: Additional keyword arguments for ``HTTPClient``.

        Returns:
            An initialized instance of the calling class.
        """
        client = cls(proxy=proxy)

        await client._setup(**kwargs)

        return client

    @classmethod
    async def from_cookies(
        cls,
        cookies: str | list[Mapping[str, Any]],
        *,
        proxy: str | None = None,
        language: str = "en",
        **kwargs: Unpack[_AsyncClientOptions],
    ) -> Self:
        """Create a managed cookie-authenticated client with optional transport settings."""
        from .session import AuthSession, normalize_language

        language = normalize_language(language)
        kwargs.setdefault(
            "emulation",
            wreq.Emulation(platform=wreq.Platform.Windows, profile=wreq.Profile.Chrome147),
        )
        client = await cls.new(proxy=proxy, **kwargs)

        try:
            session = await AuthSession.from_cookies(cookies, client=client, language=language)
        except BaseException:
            await client.close()
            raise
        client._session = session

        return client

    @property
    def session(self) -> AuthSession:
        """Return the managed authentication session; require authorization first."""
        if self._session is None:
            raise RuntimeError("Use AsyncClient.from_cookies() for an authorized client")

        return self._session

    async def __aenter__(self) -> Self:
        """Open the transports and return this client."""
        await self._setup()

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the transports without suppressing context exceptions."""
        try:
            await self.close()
        except Exception as exc:
            if isinstance(exc_value, asyncio.CancelledError):
                raise exc_value from exc

            raise

    async def close(self) -> None:
        """Close both transports; concurrent callers share the same shutdown."""
        task = self._close_task

        if task is None:
            http, websocket = self._http, self._ws
            self._http = self._ws = None

            if http is None and websocket is None:
                return

            session, self._session = self._session, None

            async def shutdown() -> None:
                """Finish the owned shutdown task even when its caller is cancelled."""
                try:
                    if session is not None:
                        await session.stop_refresh()
                finally:
                    await _close_transports(http, websocket)

            task = asyncio.create_task(shutdown(), name="spotapi-client-close")
            self._close_task = task

            task.add_done_callback(_observe_shutdown)

        try:
            await asyncio.shield(task)
        finally:
            if task.done() and self._close_task is task:
                self._close_task = None

    async def _setup(self, **kwargs: Unpack[_AsyncClientOptions]) -> None:
        """Initialize the transports once, cleaning up on setup failure."""
        close_task = self._close_task

        if close_task is not None:
            await asyncio.shield(close_task)

            if self._close_task is close_task:
                self._close_task = None

        if self._http is not None:
            return

        if self._proxy:
            kwargs["proxies"] = [wreq.Proxy.all(self._proxy)]

        http = HTTPClient(**kwargs)

        try:
            websocket = WebSocketClient(
                http_client=http, logger=kwargs.get("logger") or DefaultLogger
            )

            websocket.start_pinging()
        except Exception:
            await http.close()

            raise

        self._http, self._ws = http, websocket

    def _require_http(self) -> HTTPClient:
        """Return the open HTTP transport or raise ``RuntimeError``."""
        if self._http is None:
            raise RuntimeError("Client is not open; use AsyncClient.new() or async with")

        return self._http

    async def request(
        self,
        method: Methods,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a validated request.

        Args:
            method: HTTP method.
            url: Request URL.
            max_attempts: Retry limit; use ``1`` for operations that must not be replayed.
                An explicit larger value permits replay.
            retry_safe: Enable retries for a known read-only operation such as
                a catalogue POST. Defaults to safe HTTP methods only.
            **kwargs: Options forwarded to ``wreq``.

        Returns:
            The validated HTTP response.

        Raises:
            RuntimeError: If this client is not open.
            ValueError: If ``max_attempts`` is less than one.
            HTTPError: If the response is unsuccessful or JSON is invalid.
        """
        session = self._session
        provided = kwargs.get("headers")
        headers: Mapping[str, str] = provided if isinstance(provided, Mapping) else {}
        token = session.token.access_token if session is not None else None
        authorized = (
            token is not None
            and headers.get("authorization", headers.get("Authorization")) == f"Bearer {token}"
        )
        safe = retry_safe is True or (retry_safe is None and method in {"GET", "HEAD", "OPTIONS"})

        response = await self._require_http().request(
            method, url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )

        if response.status_code.as_int() == 401 and authorized and safe and session is not None:
            await session.refresh(previous_token=token)
            renewed = session.authorized_headers
            kwargs["headers"] = {
                **{
                    key: value
                    for key, value in headers.items()
                    if key.casefold() not in {"authorization", "client-token"}
                },
                "authorization": renewed["authorization"],
                "client-token": renewed["client-token"],
            }
            response = await self._require_http().request(
                method, url, max_attempts=1, retry_safe=retry_safe, **kwargs
            )

        return _validate(response)

    async def get(
        self,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a GET request with an optional per-request retry limit."""
        return await self.request(
            "GET", url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )

    async def post(
        self,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a POST request with an optional per-request retry limit."""
        return await self.request(
            "POST", url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )

    async def put(
        self,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a PUT request with an optional per-request retry limit."""
        return await self.request(
            "PUT", url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )

    async def delete(
        self,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a DELETE request with an optional per-request retry limit."""
        return await self.request(
            "DELETE", url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )

    async def head(
        self,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a HEAD request with an optional per-request retry limit."""
        return await self.request(
            "HEAD", url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )

    async def patch(
        self,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a PATCH request with an optional per-request retry limit."""
        return await self.request(
            "PATCH", url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )


def _validate(response: Response) -> Response:
    """Validate and return the original response.

    Args:
        response: Response returned by the underlying HTTP transport.

    Returns:
        The response after all validation checks succeed.

    Raises:
        HTTPError: If the status is unsuccessful, or a JSON response
            has no parsed object payload.
    """
    if not response.ok:
        raise HTTPError(
            f"Request returned non-ok status code: {response.status_code.as_int()}",
            status_code=response.status_code.as_int(),
            response=response,
        )

    content_type = response.headers.get("content-type")

    if content_type and "json" in content_type and response.json is None:
        raise HTTPError(
            "Expected a JSON payload but received an empty or invalid body", response=response
        )

    return response
