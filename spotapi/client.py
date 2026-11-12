"""Asynchronous HTTP and WebSocket client with validated HTTP responses."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from types import TracebackType
from typing import TYPE_CHECKING, Any, Self, Unpack, cast
from urllib.parse import urlsplit

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
    and validate responses unless a non-success status is explicitly expected.
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
        return f"<AsyncClient open={self._http is not None} proxy={self._proxy is not None}>"

    @property
    def transport(self) -> HTTPClient:
        """The open HTTP transport, returning responses without status validation.

        Use this for protocols that interpret non-success statuses themselves.
        Prefer :meth:`request` for ordinary validated HTTP requests.

        Raises:
            RuntimeError: If the client is not open.
        """
        if self._http is None:
            raise RuntimeError("Client is not open; use AsyncClient.new() or async with")
        return self._http

    @property
    def websocket(self) -> WebSocketClient:
        """The open WebSocket transport; call its ``connect()`` to attach a socket.

        Raises:
            RuntimeError: If the client is not open.
        """
        if self._ws is None:
            raise RuntimeError("Client is not open; use AsyncClient.new() or async with")
        return self._ws

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
        """Open and authorize a client that owns token renewal and transports.

        Args:
            cookies: Cookie-header text or exported browser-cookie records.
            proxy: Optional transport proxy URL.
            language: Language tag used for Spotify requests.
            **kwargs: HTTP transport configuration, including retry settings.

        Returns:
            An open authenticated client. Close it with await client.close().

        Initialization failure closes the client before propagating the error.
        Use it with account/player helpers without constructing another session.
        """
        from .session import AuthSession, normalize_language

        language = normalize_language(language)
        kwargs.setdefault(
            "emulation",
            wreq.Emulation(platform=wreq.Platform.Windows, profile=wreq.Profile.Chrome147),
        )
        client = await cls.new(proxy=proxy, **kwargs)

        try:
            await AuthSession.from_cookies(cookies, client=client, language=language)
        except BaseException:
            await client.close()
            raise

        return client

    @property
    def session(self) -> AuthSession:
        """Return the managed authentication session; require authorization first."""
        if self._session is None:
            raise RuntimeError(
                "Client has no authentication session; use from_cookies() or AuthSession(client)"
            )

        return self._session

    @session.setter
    def session(self, session: AuthSession) -> None:
        """Attach this client's authentication owner; reject conflicting sessions."""
        if session.client is not self:
            raise ValueError("The authentication session belongs to another client")
        if self._session is not None and self._session is not session:
            raise RuntimeError("This client already has an authentication session")
        self._session = session

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

    async def request(
        self,
        method: Methods,
        url: str,
        *,
        authorized: bool = False,
        expected_statuses: tuple[int, ...] = (),
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a request with optional managed Spotify authorization.

        Args:
            method: HTTP method.
            url: Absolute request URL. Managed credentials require an HTTPS
                Spotify host without embedded user credentials.
            authorized: Add the session's current headers and renew once after
                a 401 for a replay-safe request. Requires an attached session.
            expected_statuses: Additional statuses that the caller handles, such
                as 404 when removing an already absent device.
            max_attempts: Total transport attempts. Setting this to 1 also
                disables automatic credential-renewal replay.
            retry_safe: Permit replay of a known read-only operation, including
                catalogue POSTs. Defaults to safe HTTP methods.
            **kwargs: Native transport options. Managed requests disable redirects
                to prevent forwarding credentials. Header names are merged without
                case distinctions; managed credential headers cannot be replaced.

        Returns:
            A successful response, or an explicitly expected status.

        Raises:
            RuntimeError: The client is closed or authorization is unavailable.
            ValueError: Credentials target an invalid host or are overridden.
            HTTPError: The request fails or returns an invalid JSON object.
        """
        if type(authorized) is not bool:
            raise TypeError("authorized must be a boolean")
        if any(
            type(status) is not int or not 100 <= status <= 599 for status in expected_statuses
        ):
            raise ValueError("expected_statuses must contain HTTP status integers")

        session = self.session if authorized else None
        token: str | None = None
        extra_headers: dict[str, str] = {}
        if session is not None:
            _require_spotify_url(url)
            token = session.token.access_token
            extra_headers = _extra_headers(kwargs.get("headers"))
            kwargs["headers"] = {**session.authorized_headers, **extra_headers}
            # Custom client-token headers must not follow a redirect to another origin.
            kwargs["redirect"] = wreq.redirect.Policy.none()

        response = await self.transport.request(
            method, url, max_attempts=max_attempts, retry_safe=retry_safe, **kwargs
        )
        status = response.status_code.as_int()
        safe = retry_safe is True or (
            retry_safe is None and method in {"GET", "HEAD", "OPTIONS", "TRACE"}
        )
        if (
            status == 401
            and status not in expected_statuses
            and session is not None
            and safe
            and max_attempts != 1
        ):
            await session.refresh(previous_token=token)
            kwargs["headers"] = {**session.authorized_headers, **extra_headers}
            response = await self.transport.request(
                method, url, max_attempts=1, retry_safe=retry_safe, **kwargs
            )

        return _validate(response, method=method, expected_statuses=expected_statuses)

    async def get(
        self,
        url: str,
        *,
        authorized: bool = False,
        expected_statuses: tuple[int, ...] = (),
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a GET request and validate the response.

        Args:
            url: Absolute request URL.
            authorized: Attach managed Spotify credentials; redirects are disabled.
            expected_statuses: Additional statuses handled by the caller.
            max_attempts: Transport attempt limit; 1 also disables auth replay.
            retry_safe: Override method-based replay safety for this operation.
            **kwargs: Native request options, including query, headers and body.

        Returns:
            The validated response, or an explicitly expected status.

        See request() for authorization, replay rules and raised errors.
        """
        return await self.request(
            "GET",
            url,
            authorized=authorized,
            expected_statuses=expected_statuses,
            max_attempts=max_attempts,
            retry_safe=retry_safe,
            **kwargs,
        )

    async def post(
        self,
        url: str,
        *,
        authorized: bool = False,
        expected_statuses: tuple[int, ...] = (),
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a POST request and validate the response.

        Args:
            url: Absolute request URL.
            authorized: Attach managed Spotify credentials; redirects are disabled.
            expected_statuses: Additional statuses handled by the caller.
            max_attempts: Transport attempt limit; 1 also disables auth replay.
            retry_safe: Override method-based replay safety for this operation.
            **kwargs: Native request options, including query, headers and body.

        Returns:
            The validated response, or an explicitly expected status.

        See request() for authorization, replay rules and raised errors.
        """
        return await self.request(
            "POST",
            url,
            authorized=authorized,
            expected_statuses=expected_statuses,
            max_attempts=max_attempts,
            retry_safe=retry_safe,
            **kwargs,
        )

    async def put(
        self,
        url: str,
        *,
        authorized: bool = False,
        expected_statuses: tuple[int, ...] = (),
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a PUT request and validate the response.

        Args:
            url: Absolute request URL.
            authorized: Attach managed Spotify credentials; redirects are disabled.
            expected_statuses: Additional statuses handled by the caller.
            max_attempts: Transport attempt limit; 1 also disables auth replay.
            retry_safe: Override method-based replay safety for this operation.
            **kwargs: Native request options, including query, headers and body.

        Returns:
            The validated response, or an explicitly expected status.

        See request() for authorization, replay rules and raised errors.
        """
        return await self.request(
            "PUT",
            url,
            authorized=authorized,
            expected_statuses=expected_statuses,
            max_attempts=max_attempts,
            retry_safe=retry_safe,
            **kwargs,
        )

    async def delete(
        self,
        url: str,
        *,
        authorized: bool = False,
        expected_statuses: tuple[int, ...] = (),
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a DELETE request and validate the response.

        Args:
            url: Absolute request URL.
            authorized: Attach managed Spotify credentials; redirects are disabled.
            expected_statuses: Additional statuses handled by the caller.
            max_attempts: Transport attempt limit; 1 also disables auth replay.
            retry_safe: Override method-based replay safety for this operation.
            **kwargs: Native request options, including query, headers and body.

        Returns:
            The validated response, or an explicitly expected status.

        See request() for authorization, replay rules and raised errors.
        """
        return await self.request(
            "DELETE",
            url,
            authorized=authorized,
            expected_statuses=expected_statuses,
            max_attempts=max_attempts,
            retry_safe=retry_safe,
            **kwargs,
        )

    async def head(
        self,
        url: str,
        *,
        authorized: bool = False,
        expected_statuses: tuple[int, ...] = (),
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a HEAD request and validate the response.

        Args:
            url: Absolute request URL.
            authorized: Attach managed Spotify credentials; redirects are disabled.
            expected_statuses: Additional statuses handled by the caller.
            max_attempts: Transport attempt limit; 1 also disables auth replay.
            retry_safe: Override method-based replay safety for this operation.
            **kwargs: Native request options, including query, headers and body.

        Returns:
            The validated response, or an explicitly expected status.

        See request() for authorization, replay rules and raised errors.
        """
        return await self.request(
            "HEAD",
            url,
            authorized=authorized,
            expected_statuses=expected_statuses,
            max_attempts=max_attempts,
            retry_safe=retry_safe,
            **kwargs,
        )

    async def patch(
        self,
        url: str,
        *,
        authorized: bool = False,
        expected_statuses: tuple[int, ...] = (),
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a PATCH request and validate the response.

        Args:
            url: Absolute request URL.
            authorized: Attach managed Spotify credentials; redirects are disabled.
            expected_statuses: Additional statuses handled by the caller.
            max_attempts: Transport attempt limit; 1 also disables auth replay.
            retry_safe: Override method-based replay safety for this operation.
            **kwargs: Native request options, including query, headers and body.

        Returns:
            The validated response, or an explicitly expected status.

        See request() for authorization, replay rules and raised errors.
        """
        return await self.request(
            "PATCH",
            url,
            authorized=authorized,
            expected_statuses=expected_statuses,
            max_attempts=max_attempts,
            retry_safe=retry_safe,
            **kwargs,
        )


def _validate(
    response: Response,
    *,
    method: Methods | None = None,
    expected_statuses: tuple[int, ...] = (),
) -> Response:
    """Validate and return the original response.

    Args:
        response: Response returned by the underlying HTTP transport.

    Returns:
        The response after all validation checks succeed.

    Raises:
        HTTPError: If the status is unsuccessful, or a JSON response
            has no parsed object payload.
    """
    status = response.status_code.as_int()
    if status in expected_statuses and not response.ok:
        return response
    if not response.ok:
        raise HTTPError(
            f"Request returned non-ok status code: {response.status_code.as_int()}",
            status_code=response.status_code.as_int(),
            response=response,
        )

    content_type = response.headers.get("content-type")

    body_allowed = method != "HEAD" and status not in {204, 205}
    if (
        body_allowed
        and content_type
        and "json" in content_type.casefold()
        and response.json is None
    ):
        raise HTTPError(
            "Expected a JSON payload but received an empty or invalid body", response=response
        )

    return response


def _require_spotify_url(url: str) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold().rstrip(".")
    if (
        parsed.scheme != "https"
        or not (host == "spotify.com" or host.endswith(".spotify.com"))
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise ValueError("Managed authorization requires an HTTPS Spotify endpoint")


def _extra_headers(provided: object) -> dict[str, str]:
    if provided is not None and not isinstance(provided, Mapping):
        raise TypeError("Authorized request headers must be a string mapping")
    extra: dict[str, str] = {}
    if isinstance(provided, Mapping):
        for key, value in cast(Mapping[object, object], provided).items():
            if not isinstance(key, str) or not isinstance(value, str):
                raise TypeError("Authorized request headers must contain strings")
            extra[key.casefold()] = value
    if extra.keys() & {"authorization", "client-token"}:
        raise ValueError("Managed authorization headers cannot be overridden")
    return extra
