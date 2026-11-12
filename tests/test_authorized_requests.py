"""Managed credential policy through a transport-shaped fake, without native I/O."""

from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import AsyncClient, AuthSession
from spotapi.connection import HTTPClient, Response
from spotapi.connection.types import Methods
from spotapi.datastruct import ObjectDict
from spotapi.session import AccessToken
from spotapi.types import HTTPError


def response(status: int) -> Mock:
    return Mock(
        spec=Response,
        status_code=Mock(as_int=Mock(return_value=status)),
        ok=200 <= status < 300,
        headers={},
        json=ObjectDict(),
    )


@pytest.mark.parametrize(
    ("method", "safe", "attempts", "expected", "calls"),
    [
        ("GET", None, None, (), 2),
        ("HEAD", None, None, (), 2),
        ("POST", True, None, (), 2),
        ("POST", None, None, (), 1),
        ("GET", False, None, (), 1),
        ("GET", None, 1, (), 1),
        ("GET", None, None, (401,), 1),
    ],
)
async def test_only_replayable_authorized_requests_renew_credentials(
    method: Methods,
    safe: bool | None,
    attempts: int | None,
    expected: tuple[int, ...],
    calls: int,
) -> None:
    request = AsyncMock(side_effect=[response(401), response(200)])
    client = AsyncClient()
    client._http = Mock(spec=HTTPClient, request=request)
    session = Mock(
        spec=AuthSession,
        token=AccessToken("client", "old", 0, "old-client"),
        authorized_headers={"authorization": "Bearer old", "client-token": "old-client"},
    )
    client._session = session

    async def renew(*, previous_token: str | None) -> AccessToken:
        assert previous_token == "old"
        session.authorized_headers = {"authorization": "Bearer new", "client-token": "new-client"}
        return AccessToken("client", "new", 0, "new-client")

    session.refresh = AsyncMock(side_effect=renew)
    headers = {"X-Feature": "example"}

    async def send() -> Response:
        return await client.request(
            method,
            "https://spclient.wg.spotify.com/example",
            authorized=True,
            headers=headers,
            max_attempts=attempts,
            retry_safe=safe,
            expected_statuses=expected,
        )

    if calls == 1 and not expected:
        with pytest.raises(HTTPError):
            await send()
    else:
        await send()

    assert request.await_count == calls
    assert session.refresh.await_count == calls - 1
    assert headers == {"X-Feature": "example"}
    assert request.await_args_list[0].kwargs["headers"]["authorization"] == "Bearer old"
    if calls == 2:
        assert request.await_args_list[-1].kwargs["headers"] == {
            "authorization": "Bearer new",
            "client-token": "new-client",
            "x-feature": "example",
        }
        assert request.await_args_list[-1].kwargs["max_attempts"] == 1


async def test_plain_requests_do_not_access_uninitialized_session_tokens() -> None:
    client = AsyncClient()
    request = AsyncMock(return_value=response(200))
    client._http = Mock(spec=HTTPClient, request=request)
    AuthSession(client)

    await client.get("https://open.spotify.com/api/token")

    assert request.await_args is not None
    assert "authorization" not in request.await_args.kwargs.get("headers", {})
