"""HTTP contracts using transport-shaped fakes and real response parsing."""

from __future__ import annotations

import asyncio
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from typing import Any, Self

import pytest
import wreq

from spotapi.v2.connection.http import HTTPClient, RateLimiter, _parse_retry_after
from spotapi.v2.types import HTTPError


class Status:
    def __init__(self, value: int) -> None:
        self.value = value

    def as_int(self) -> int:
        return self.value

    def is_success(self) -> bool:
        return 200 <= self.value < 300


class RawResponse:
    def __init__(
        self,
        status: int = 200,
        *,
        headers: Iterable[tuple[bytes, bytes]] = (),
        body: str | BaseException = '{"items": []}',
    ) -> None:
        self.status = Status(status)
        self.headers = [(b"content-type", b"application/json"), *headers]
        self.body = body
        self.url = "https://example.test/"
        self.closed = False

    async def text(self) -> str:
        if isinstance(self.body, BaseException):
            raise self.body

        return self.body

    async def bytes(self) -> bytes:
        return (await self.text()).encode("utf-8")

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *args: object) -> None:
        self.closed = True


class Transport:
    def __init__(self, responses: Iterable[RawResponse | BaseException]) -> None:
        self.responses = iter(responses)
        self.calls = 0

    async def request(self, *args: object, **kwargs: Any) -> RawResponse:
        self.calls += 1
        result = next(self.responses)

        if isinstance(result, BaseException):
            raise result

        return result


def client(
    monkeypatch: pytest.MonkeyPatch,
    responses: Iterable[RawResponse | BaseException],
    **kwargs: Any,
) -> tuple[HTTPClient, Transport]:
    transport = Transport(responses)

    def create_transport(**options: Any) -> Transport:
        return transport

    monkeypatch.setattr(wreq, "Client", create_transport)

    return (
        HTTPClient(backoff=0, jitter=None, rate_limiter=RateLimiter(), **kwargs),
        transport,
    )


async def test_transient_failure_then_success_closes_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw = RawResponse()
    http, transport = client(monkeypatch, [wreq.exceptions.ConnectionError("lost"), raw])

    result = await http.get("https://example.test/")

    assert result.json is not None
    assert result.json["items"] == []
    assert raw.closed and transport.calls == 2


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
async def test_unsafe_methods_are_not_replayed(
    monkeypatch: pytest.MonkeyPatch, method: str
) -> None:
    http, transport = client(monkeypatch, [wreq.exceptions.TimeoutError("ambiguous")])

    with pytest.raises(HTTPError):
        await getattr(http, method)("https://example.test/")

    assert transport.calls == 1


async def test_read_only_post_opts_into_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    http, transport = client(monkeypatch, [RawResponse(503), RawResponse()])

    assert (await http.post("https://example.test/", retry_safe=True)).ok
    assert transport.calls == 2


async def test_last_failure_does_not_return_stale_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    http, transport = client(
        monkeypatch,
        [RawResponse(503), wreq.exceptions.TimeoutError("last")],
        max_attempts=2,
    )

    with pytest.raises(HTTPError) as raised:
        await http.get("https://example.test/")

    assert isinstance(raised.value.__cause__, wreq.exceptions.TimeoutError)
    assert transport.calls == 2


async def test_permanent_transport_error_is_normalized_without_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    error = wreq.exceptions.TlsError("bad certificate")
    http, transport = client(monkeypatch, [error])

    with pytest.raises(HTTPError) as raised:
        await http.get("https://example.test/")

    assert raised.value.__cause__ is error
    assert transport.calls == 1


async def test_programmer_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    http, _ = client(monkeypatch, [TypeError("bad option")])

    with pytest.raises(TypeError):
        await http.get("https://example.test/")


async def test_response_closed_when_read_is_cancelled(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = RawResponse(body=asyncio.CancelledError())
    http, transport = client(monkeypatch, [raw])

    with pytest.raises(asyncio.CancelledError):
        await http.get("https://example.test/")

    assert raw.closed and transport.calls == 1


async def test_429_zero_delay_retries_and_closes(monkeypatch: pytest.MonkeyPatch) -> None:
    limited = RawResponse(429, headers=[(b"retry-after", b"0")])
    http, transport = client(monkeypatch, [limited, RawResponse()])

    assert (await http.get("https://example.test/")).ok
    assert limited.closed and transport.calls == 2


async def test_long_429_returns_without_waiting(monkeypatch: pytest.MonkeyPatch) -> None:
    http, transport = client(monkeypatch, [RawResponse(429, headers=[(b"retry-after", b"3600")])])

    async with asyncio.timeout(1):
        assert (await http.get("https://example.test/")).status_code.as_int() == 429

    assert transport.calls == 1


@pytest.mark.parametrize(
    "value,expected", [("3", 3), ("-1", 0), ("nan", None), ("inf", None), ("bad", None)]
)
def test_retry_after_seconds(value: str, expected: float | None) -> None:
    assert _parse_retry_after({"retry-after": value}) == expected


def test_retry_after_http_date() -> None:
    date = format_datetime(datetime.now(UTC) + timedelta(seconds=30), usegmt=True)
    delay = _parse_retry_after({"retry-after": date})

    assert delay is not None and 28 <= delay <= 30


async def test_cancellation_interrupts_rate_limit_wait() -> None:
    limiter = RateLimiter()

    limiter.pause("EXAMPLE.test.", 30)

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await limiter.wait("example.test")


async def test_cancellation_interrupts_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    http, transport = client(monkeypatch, [RawResponse(503)])
    http._backoff = 30

    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await http.get("https://example.test/")

    assert transport.calls == 1


def test_rate_limit_state_is_bounded() -> None:
    limiter = RateLimiter()

    for number in range(1000):
        limiter.pause(str(number), 30)

    assert len(limiter._resume_at) == 128


def test_direct_and_proxy_cooldowns_have_explicit_ownership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def create_transport(**kwargs: Any) -> object:
        return object()

    monkeypatch.setattr(wreq, "Client", create_transport)

    direct = HTTPClient()
    other_direct = HTTPClient()
    proxy = HTTPClient(proxies=[wreq.Proxy.all("http://example.test:8080")])
    other_proxy = HTTPClient(proxies=[wreq.Proxy.all("http://example.test:8080")])

    assert direct._rate_limiter is other_direct._rate_limiter
    assert proxy._rate_limiter is not direct._rate_limiter
    assert proxy._rate_limiter is not other_proxy._rate_limiter
    shared = RateLimiter()
    explicit = HTTPClient(
        proxies=[wreq.Proxy.all("http://example.test:8080")], rate_limiter=shared
    )

    assert explicit._rate_limiter is shared


@pytest.mark.parametrize(
    "content_type,body",
    [(b"text/javascript", 'window.x = {"a": 1}'), (b"text/html", "<html></html>")],
)
async def test_script_and_html_are_not_parsed_as_json(
    monkeypatch: pytest.MonkeyPatch, content_type: bytes, body: str
) -> None:
    def unexpected_parse(text: str):
        raise AssertionError("non-JSON body passed to JSON parser")

    monkeypatch.setattr("spotapi.v2.connection.http._parse_json_object", unexpected_parse)

    raw = RawResponse(headers=[(b"content-type", content_type)], body=body)
    http, _ = client(monkeypatch, [raw])

    result = await http.get("https://example.test/")

    assert result.json is None and result.text == body


@pytest.mark.parametrize(
    "content_type", ["application/x-protobuf", "application/vnd.spotify.user-profile-view"]
)
async def test_binary_responses_preserve_bytes(
    monkeypatch: pytest.MonkeyPatch, content_type: str
) -> None:
    raw = RawResponse(headers=[(b"content-type", content_type.encode())], body="\x08\x01")
    http, _ = client(monkeypatch, [raw])
    result = await http.get("https://example.test/")
    assert result.body == b"\x08\x01"
    assert result.text == "" and result.json is None and raw.closed


async def test_spotify_json_media_type_is_not_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = RawResponse(
        headers=[(b"content-type", b"application/vnd.spotify.user-profile-view+json")]
    )
    http, _ = client(monkeypatch, [raw])
    result = await http.get("https://example.test/")
    assert result.json is not None and result.json["items"] == []
    assert result.body == b""
