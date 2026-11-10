"""HTTP transport, cookie management, and pooled clients for SpotAPI.

Wraps ``wreq`` with normalized responses, bounded retries, and Spotify
rate-limit handling.
"""

from __future__ import annotations

import asyncio
import json
import math
import random
import sys
import threading
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from types import TracebackType
from typing import TYPE_CHECKING, Any, ClassVar, Final, Self, Unpack, cast
from urllib.parse import urlsplit

import wreq

from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.types import DefaultLogger, HTTPError
from spotapi.v2.utils import random_with_weights

from .types import (
    DefaultOSList,
    DefaultProfileList,
    Methods,
    Response,
)

if TYPE_CHECKING:
    from wreq import ClientConfig

    from spotapi.v2.types import LoggerProtocol

    from .types import (
        BackoffStrategy,
        EmulateBrowser,
        EmulateOS,
        JitterStrategy,
    )

__all__ = ("HTTPClient", "RateLimiter")

# Statuses that are usually transient. 429 is handled separately because it
# needs a pause shared with every other request to the same host.
RETRYABLE_STATUS_CODES: Final = frozenset({408, 425, 500, 502, 503, 504})
_MAX_TRACKED_COOLDOWNS: Final[int] = 128
_MAX_COOLDOWN_SLEEP: Final[float] = 3600.0
_RETRYABLE_TRANSPORT_ERRORS: Final = (
    wreq.exceptions.ConnectionError,
    wreq.exceptions.ProxyConnectionError,
    wreq.exceptions.ConnectionResetError,
    wreq.exceptions.TimeoutError,
)
_PERMANENT_TRANSPORT_ERRORS: Final = (
    wreq.exceptions.RequestError,
    wreq.exceptions.TlsError,
    wreq.exceptions.BodyError,
    wreq.exceptions.DecodingError,
    wreq.exceptions.RedirectError,
    wreq.exceptions.StatusError,
)

_SPOTIFY_COOKIE_URLS: Final[tuple[str, ...]] = (
    "https://open.spotify.com",
    "https://www.spotify.com",
    "https://spotify.com",
    "https://accounts.spotify.com",
    "https://api.spotify.com",
    "https://api-partner.spotify.com",
    "https://spclient.wg.spotify.com",
    "https://dealer.spotify.com",
    "https://gds.spotify.com",
    "https://analytics.spotify.com",
)


def _default_backoff(attempt: int) -> float:
    """Return 1, 2, 4, 8... seconds for zero-based ``attempt``."""
    return math.ldexp(1.0, min(attempt, 1023))


def _default_jitter(base_delay: float) -> float:
    """Return an additional random delay of 5-40% of ``base_delay``."""
    return random.uniform(base_delay * 0.05, base_delay * 0.40)


class RateLimiter:
    """Pause requests to a host after it answers ``429 Too Many Requests``.

    Spotify only reveals its limits once they are hit (via ``Retry-After``), so
    a 429 pauses every request to that host. Cooldowns are bounded to 128 hosts;
    when full, the soonest-expiring entry is evicted.
    """

    __slots__ = ("_resume_at", "_lock")

    def __init__(self) -> None:
        """Create a bounded, thread-safe table of per-host rate-limit cooldowns."""
        self._resume_at: dict[str, float] = {}
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        with self._lock:
            return f"<RateLimiter active_hosts={len(self._resume_at)}>"

    async def wait(self, host: str) -> None:
        """Sleep until ``host`` may be contacted again."""
        host = host.casefold().rstrip(".")

        while True:
            with self._lock:
                resume_at = self._resume_at.get(host)

                if resume_at is None:
                    return

                remaining = resume_at - time.monotonic()

                if remaining <= 0:
                    # Another thread or loop may have extended the deadline.
                    if self._resume_at.get(host) == resume_at:
                        self._resume_at.pop(host, None)

                    continue

            await asyncio.sleep(min(remaining, _MAX_COOLDOWN_SLEEP))

    def pause(self, host: str, seconds: float) -> None:
        """Block ``host`` for at least ``seconds`` from now."""
        if isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
            raise ValueError("rate-limit delay must be finite and non-negative")

        host = host.casefold().rstrip(".")
        now = time.monotonic()
        resume_at = min(now + seconds, sys.float_info.max)

        with self._lock:
            if host not in self._resume_at and len(self._resume_at) >= _MAX_TRACKED_COOLDOWNS:
                expired = [key for key, value in self._resume_at.items() if value <= now]

                for key in expired:
                    self._resume_at.pop(key, None)

                if len(self._resume_at) >= _MAX_TRACKED_COOLDOWNS:
                    soonest = min(self._resume_at, key=self._resume_at.__getitem__)

                    self._resume_at.pop(soonest)

            self._resume_at[host] = max(self._resume_at.get(host, 0.0), resume_at)


class HTTPClient:
    """Wrap ``wreq.Client`` with response normalization, retries, and rate limiting.

    Args:
        backoff: Fixed delay or callback receiving the zero-based attempt index.
        jitter: Fixed additional delay, callback receiving the base delay, or
            ``None`` to disable jitter.
        max_attempts: Default number of attempts per request, including the first.
        max_delay: Longest wait in seconds between attempts. A 429 whose
            ``Retry-After`` exceeds this is returned to the caller, not waited out.
        rate_limiter: Cooldown tracker shared by clients on the same IP.
            Direct clients share one by default; proxied clients get a private one.
        logger: Logger implementing the SpotAPI logger protocol.
        **kwargs: Options passed to ``wreq.Client``. An emulation profile is
            selected automatically when ``emulation`` is omitted or ``None``.

    Note:
        The client owns its underlying ``wreq.Client``. Prefer ``async with``
        or call :meth:`close` when finished.
    """

    _default_client_cfg: ClassVar[ClientConfig] = {
        "cookie_store": True,
        "gzip": True,
        "referer": True,
        "brotli": True,
        "deflate": True,
        "zstd": True,
        "timeout": timedelta(seconds=30),
        "redirect": wreq.redirect.Policy.limited(10),
    }

    __slots__ = (
        "_wclient",
        "_logger",
        "_backoff",
        "_jitter",
        "_max_attempts",
        "_max_delay",
        "_rate_limiter",
    )

    def __init__(
        self,
        *,
        backoff: BackoffStrategy = _default_backoff,
        jitter: JitterStrategy = _default_jitter,
        max_attempts: int = 3,
        max_delay: float = 60.0,
        rate_limiter: RateLimiter | None = None,
        logger: LoggerProtocol = DefaultLogger,
        **kwargs: Unpack[ClientConfig],
    ) -> None:
        """Configure bounded HTTP concurrency, retry timing and native transport ownership."""
        if type(max_attempts) is not int or max_attempts < 1:
            raise ValueError("max_attempts must be a positive integer")

        if isinstance(max_delay, bool) or not math.isfinite(max_delay) or max_delay < 0:
            raise ValueError("max_delay must be a finite, non-negative number")

        if isinstance(backoff, (int, float)) and (
            isinstance(backoff, bool) or not math.isfinite(backoff) or backoff < 0
        ):
            raise ValueError("backoff must be finite and non-negative")

        if isinstance(jitter, (int, float)) and (
            isinstance(jitter, bool) or not math.isfinite(jitter) or jitter < 0
        ):
            raise ValueError("jitter must be finite and non-negative")

        if kwargs.get("emulation") is None:
            kwargs["emulation"] = _random_emulation()

        self._wclient = wreq.Client(**{**self._default_client_cfg, **kwargs})
        self._logger = logger
        self._backoff = backoff
        self._jitter = jitter
        self._max_attempts = max_attempts
        self._max_delay = max_delay

        if rate_limiter is None:
            rate_limiter = RateLimiter() if kwargs.get("proxies") else _shared_rate_limiter

        self._rate_limiter = rate_limiter

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<HTTPClient max_attempts={self._max_attempts}>"

    async def __aenter__(self) -> Self:
        """Enter this resource's asynchronous ownership scope."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release resources owned by this asynchronous scope."""
        try:
            await self.close()
        except Exception as exc:
            if isinstance(exc_value, asyncio.CancelledError):
                raise exc_value from exc

            raise

    async def close(self) -> None:
        """Close the underlying ``wreq.Client``."""
        self._wclient.close()

    @property
    def wclient(self) -> wreq.Client:
        """The underlying ``wreq.Client`` for advanced operations."""
        return self._wclient

    def get_cookie(self, name: str) -> str | None:
        """Find the first cookie with a case-insensitive name, regardless of domain."""
        jar = self._wclient.cookie_jar

        if jar is None:
            return None

        name_lower = name.lower()

        for cookie in jar.get_all():
            if cookie.name.lower() == name_lower:
                return cookie.value

        return None

    def get_all_cookies(self) -> list[dict[str, Any]]:
        """Return stored cookies as ``wreq.Cookie`` constructor mappings.

        The result is suitable for :meth:`set_cookies`. It is empty when the
        cookie jar is disabled.
        """
        jar = self._wclient.cookie_jar

        if jar is None:
            return []

        cookies: list[dict[str, Any]] = []

        for cookie in jar.get_all():
            # ``wreq.Cookie`` exposes attributes, not a mapping interface.
            data: dict[str, Any] = {
                "name": cookie.name,
                "value": cookie.value,
                "domain": cookie.domain,
                "path": cookie.path,
                "max_age": cookie.max_age,
                "expires": cookie.expires,
                "http_only": cookie.http_only,
                "secure": cookie.secure,
            }

            if cookie.same_site_lax:
                data["same_site"] = wreq.SameSite.Lax
            elif cookie.same_site_strict:
                data["same_site"] = wreq.SameSite.Strict

            cookies.append(data)

        return cookies

    def set_cookies(self, cookies: Sequence[Mapping[str, Any]]) -> None:
        """Add each cookie for every Spotify domain used by the transport."""
        jar = self._wclient.cookie_jar

        if jar is None:
            return

        for data in cookies:
            cookie = wreq.Cookie(**data)

            for url in _SPOTIFY_COOKIE_URLS:
                jar.add(cookie, url)

    async def request(
        self,
        method: Methods,
        url: str,
        *,
        max_attempts: int | None = None,
        retry_safe: bool | None = None,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        """Send a request, retrying transient failures and honoring rate limits.

        Args:
            method: HTTP method.
            url: URL to request.
            max_attempts: Explicit attempts for this call, including the first.
                Overrides the safety default; setting this above one permits
                replay. Prefer ``retry_safe=True`` for known read-only POSTs.
            retry_safe: Whether this operation can be replayed. Defaults to
                true for GET/HEAD/OPTIONS/TRACE, false for other methods.
                Safe operations use the client's default attempt count.
            **kwargs: Options forwarded to ``wreq.Client.request``.

        Returns:
            The first response that is not retryable. If attempts run out, the
            last response received is returned, so check :attr:`Response.ok`.

        Note:
            Spotify also uses POST for read-only queries, so retry safety is
            controlled per operation rather than inferred from the HTTP method.

        Raises:
            ValueError: If ``max_attempts`` is not a positive integer.
            HTTPError: If all retryable attempts fail without a response.
            HTTPError: For permanent transport failures, with the original
                exception available as the cause. Programmer errors propagate.
        """
        if retry_safe is None:
            retry_safe = method in {"GET", "HEAD", "OPTIONS", "TRACE"}

        attempts = (
            (self._max_attempts if retry_safe else 1) if max_attempts is None else max_attempts
        )

        if type(attempts) is not int or attempts < 1:
            raise ValueError("max_attempts must be a positive integer")

        host = (urlsplit(url).hostname or "").casefold()
        response: Response | None = None
        error: Exception | None = None

        for attempt in range(attempts):
            await self._rate_limiter.wait(host)

            try:
                raw = await self._wclient.request(getattr(wreq.Method, method), url, **kwargs)

                async with raw:
                    current_response = await _to_response(raw)
            except _RETRYABLE_TRANSPORT_ERRORS as exc:
                response = None
                error = exc

                self._logger.debug("Transient transport failure", attempt=attempt)

                if attempt == attempts - 1:
                    raise HTTPError(f"Request failed after {attempts} attempts") from exc

                delay = self._compute_delay(attempt)
            except _PERMANENT_TRANSPORT_ERRORS as exc:
                raise HTTPError(
                    "HTTP transport failed; check the connection and client settings"
                ) from exc
            else:
                response = current_response
                status = current_response.status_code.as_int()

                if status == 429:
                    retry_after = _parse_retry_after(current_response.headers)

                    if retry_after is not None and retry_after > self._max_delay:
                        # Return promptly, but respect the server's cooldown
                        # for other clients sharing this rate limiter.
                        self._rate_limiter.pause(host, retry_after)

                        return current_response

                    delay = self._compute_delay(attempt) if retry_after is None else retry_after

                    self._rate_limiter.pause(host, delay)
                elif status in RETRYABLE_STATUS_CODES:
                    if attempt == attempts - 1:
                        return current_response

                    delay = self._compute_delay(attempt)
                else:
                    return current_response

            if attempt < attempts - 1:
                self._logger.debug("Retrying request", host=host, attempt=attempt, delay=delay)
                await asyncio.sleep(delay)

        if response is None:
            raise HTTPError(f"Request failed after {attempts} attempts") from error

        return response

    def _compute_delay(self, attempt: int) -> float:
        """Return the jittered delay for ``attempt``, capped at ``max_delay``."""
        base = self._backoff if isinstance(self._backoff, (int, float)) else self._backoff(attempt)

        if isinstance(base, bool) or not math.isfinite(base) or base < 0:
            raise ValueError("backoff must return a finite, non-negative delay")

        jitter = 0.0

        if self._jitter is not None:
            jitter = self._jitter if isinstance(self._jitter, (int, float)) else self._jitter(base)

        if isinstance(jitter, bool) or not math.isfinite(jitter) or jitter < 0:
            raise ValueError("jitter must return a finite, non-negative delay")

        return min(base + jitter, self._max_delay)

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


async def _to_response(raw: wreq.Response) -> Response:
    """Convert a ``wreq`` response into a SpotAPI ``Response``."""
    headers = {
        bytes(key).decode("latin-1").lower(): bytes(value).decode("latin-1")
        for key, value in raw.headers
    }
    content_type = headers.get("content-type", "").casefold()
    binary = "json" not in content_type and (
        "protobuf" in content_type
        or content_type.startswith(
            ("application/vnd.spotify.", "application/octet-stream", "image/", "audio/", "video/")
        )
    )
    body = bytes(await raw.bytes()) if binary else b""
    text = "" if binary else await raw.text()
    looks_like_json = (
        text[:256].lstrip().startswith("{")
        and "javascript" not in content_type
        and "text/html" not in content_type
    )
    json_body = _parse_json_object(text) if "json" in content_type or looks_like_json else None

    return Response(
        status_code=raw.status,
        text=text,
        url=str(raw.url),
        headers=headers,
        json=json_body,
        body=body,
    )


def _parse_json_object(text: str) -> ObjectDict | None:
    """Parse ``text`` as a JSON object, returning ``None`` for anything else."""
    try:
        data = json.loads(text)
    except ValueError:
        return None

    if isinstance(data, dict):
        return ObjectDict.from_json(cast("dict[str, Any]", data))

    return None


def _parse_retry_after(headers: Mapping[str, str]) -> float | None:
    """Read ``Retry-After`` as seconds, or ``None`` if absent or not a number."""
    value = headers.get("retry-after")

    if value is None:
        return None

    try:
        seconds = float(value)
    except ValueError:
        try:
            date = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None

        if date.tzinfo is None:
            date = date.replace(tzinfo=UTC)

        seconds = (date - datetime.now(UTC)).total_seconds()

    return max(0.0, seconds) if math.isfinite(seconds) else None


def _random_emulation(
    os_list: Sequence[EmulateOS] = DefaultOSList,
    profiles: Sequence[EmulateBrowser] = DefaultProfileList,
) -> wreq.Emulation:
    """Pick a weighted browser profile and operating system.

    Raises:
        RuntimeError: If the chosen browser has no ``wreq`` profile in its
            configured version range.
    """
    selected_os = random_with_weights(os_list, [o.weight for o in os_list])
    browser = random_with_weights(profiles, [p.weight for p in profiles])

    prefix = browser.browser_name.capitalize()
    candidates: list[tuple[wreq.Profile, int]] = []

    # Profile members are named after their browser and version, e.g. ``Chrome131``.
    for name in wreq.Profile.__dict__:
        suffix = name[len(prefix) :]

        if name.startswith(prefix) and suffix.isdigit():
            version = int(suffix)

            if browser.min_version <= version <= browser.max_version:
                candidates.append((cast(wreq.Profile, getattr(wreq.Profile, name)), version))

    if not candidates:
        raise RuntimeError(f"No supported {browser.browser_name} emulation profile")

    # Exponentially favor newer browser versions.
    newest_version = max(version for _, version in candidates)
    profile = random.choices(
        [p for p, _ in candidates],
        weights=[math.exp((version - newest_version) / 5) for _, version in candidates],
    )[0]

    return wreq.Emulation(platform=selected_os.platform, profile=profile)


# Direct clients share one IP, so they share one rate limiter.
_shared_rate_limiter = RateLimiter()
