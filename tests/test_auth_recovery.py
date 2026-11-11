"""Credential renewal, cookie identity and safe replay boundaries."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import AsyncClient, Catalogue
from spotapi.connection import HTTPClient, Response
from spotapi.connection.types import Methods
from spotapi.datastruct import ObjectDict
from spotapi.query import QueryClient
from spotapi.session import AccessToken, AuthSession
from spotapi.types import HTTPError


def response(status: int) -> Mock:
    return Mock(
        spec=Response,
        status_code=Mock(as_int=Mock(return_value=status)),
        ok=200 <= status < 300,
        headers={},
        json=ObjectDict({}),
    )


@pytest.mark.parametrize(
    ("method", "retry_safe", "expected_calls"),
    [("GET", None, 2), ("POST", True, 2), ("POST", None, 1), ("GET", False, 1)],
)
async def test_only_authenticated_reads_can_refresh_and_replay(
    monkeypatch: pytest.MonkeyPatch,
    method: Methods,
    retry_safe: bool | None,
    expected_calls: int,
) -> None:
    request = AsyncMock(side_effect=[response(401), response(200)])
    monkeypatch.setattr(HTTPClient, "request", request)
    session = Mock(
        spec=AuthSession,
        token=AccessToken("client", "old", 0, "old-client"),
        authorized_headers={"authorization": "Bearer new", "client-token": "new-client"},
    )

    async with AsyncClient() as client:
        client._session = session
        headers = {
            "Authorization": "Bearer old",
            "Client-Token": "old-client",
            "accept": "application/json",
        }
        if expected_calls == 1:
            with pytest.raises(HTTPError):
                await client.request(
                    method,
                    "https://spclient.wg.spotify.com/example",
                    headers=headers,
                    retry_safe=retry_safe,
                )
        else:
            await client.request(
                method,
                "https://spclient.wg.spotify.com/example",
                headers=headers,
                retry_safe=retry_safe,
            )

        assert request.await_count == expected_calls
        assert session.refresh.await_count == expected_calls - 1
        if expected_calls == 2:
            renewed = request.await_args_list[-1].kwargs["headers"]
            assert renewed == {
                "authorization": "Bearer new",
                "client-token": "new-client",
                "accept": "application/json",
            }
            assert request.await_args_list[-1].kwargs["max_attempts"] == 1


async def test_concurrent_rejections_issue_one_new_token(monkeypatch: pytest.MonkeyPatch) -> None:
    session = AuthSession(Mock(spec=AsyncClient))
    session._token = AccessToken("client", "old", 0)
    renewed = AccessToken("client", "new", int((time.time() + 3600) * 1000), "client-token")
    issued = 0

    async def issue(self: AuthSession) -> AccessToken:
        nonlocal issued
        issued += 1
        await asyncio.sleep(0)
        return renewed

    monkeypatch.setattr(AuthSession, "_issue_token", issue)
    try:
        results = await asyncio.gather(*(session.refresh(previous_token="old") for _ in range(16)))
        assert issued == 1 and all(result is renewed for result in results)
    finally:
        await session.stop_refresh()


async def test_permanent_refresh_failure_stops_without_a_retry_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AuthSession(Mock(spec=AsyncClient))
    session._token = AccessToken("client", "old", 0)
    issue = AsyncMock(side_effect=HTTPError("Unauthorized", status_code=401))
    monkeypatch.setattr(AuthSession, "_issue_token", issue)
    monkeypatch.setattr("spotapi.session._MIN_REFRESH_DELAY", 0.001)

    with pytest.raises(HTTPError):
        await asyncio.wait_for(session._auto_refresh(), 0.1)
    issue.assert_awaited_once()


async def test_cookie_login_rejects_silent_guest_fallback_and_closes_its_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=AsyncClient)
    client.close = AsyncMock()

    async def guest(self: AuthSession) -> AccessToken:
        return AccessToken("client", "guest", 0, is_anonymous=True)

    monkeypatch.setattr(AuthSession, "authorize", guest)
    with pytest.raises(HTTPError, match="guest"):
        await AuthSession.from_cookies("sp_dc=test", client=client)
    client.close.assert_awaited_once()


async def test_token_refresh_cannot_demote_an_authenticated_session_to_guest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = AuthSession(Mock(spec=AsyncClient))
    original = AccessToken("client", "user", 0, is_anonymous=False)
    session._token = original
    session._require_user = True
    monkeypatch.setattr(
        AuthSession,
        "_issue_token",
        AsyncMock(return_value=AccessToken("client", "guest", 0, is_anonymous=True)),
    )

    with pytest.raises(HTTPError, match="guest"):
        await session.refresh(previous_token="user")
    assert session.token is original


async def test_empty_cookie_factory_closes_even_before_session_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = Mock(spec=AsyncClient, close=AsyncMock())
    monkeypatch.setattr(AsyncClient, "new", AsyncMock(return_value=client))

    with pytest.raises(ValueError, match="sp_dc"):
        await AsyncClient.from_cookies("")
    client.close.assert_awaited_once()


async def test_authenticated_catalogue_borrows_the_session_and_drains_its_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = Mock(spec=AuthSession)
    expected = ObjectDict({"me": {"profile": {"name": "Listener"}}})

    async def query(
        self: QueryClient,
        variables: dict[str, object],
        operation_name: str,
        *,
        max_attempts: int | None = None,
    ) -> ObjectDict:
        assert self.session is session
        return expected

    monkeypatch.setattr(QueryClient, "pathfinder_query", query)
    async with Catalogue(session) as catalogue:
        assert await catalogue.queries.query("profileAttributes", {}) is expected

    session.close.assert_not_called()
    with pytest.raises(RuntimeError, match="not open"):
        _ = catalogue.queries


def test_language_validation_and_switching_do_not_make_requests() -> None:
    client = Mock(spec=AsyncClient)
    session = AuthSession(client, language="fr_CA")
    assert session.language == "fr-CA"
    session.language = "de-DE"
    assert session.language == "de-DE"
    client.get.assert_not_called()

    with pytest.raises(ValueError, match="language"):
        Catalogue(language="en\r\nauthorization: bad")


async def test_client_token_grant_allows_bounded_transient_retries() -> None:
    client = Mock(spec=AsyncClient)
    client.post = AsyncMock(
        return_value=Mock(json=ObjectDict({"granted_token": {"token": "synthetic-token"}}))
    )
    session = AuthSession(client)
    session.session = Mock(server_config=Mock(client_version="test"))
    assert await session._fetch_client_token("client-id") == "synthetic-token"
    client.post.assert_awaited_once()
    assert client.post.call_args.kwargs["retry_safe"] is True
