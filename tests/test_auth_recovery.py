"""Credential renewal, cookie identity and safe replay boundaries."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import AsyncClient, Catalogue
from spotapi._protocol.totp import extract_totp_secret, generate_totp
from spotapi.connection import HTTPClient, Response
from spotapi.connection.types import Methods
from spotapi.datastruct import ObjectDict
from spotapi.query import QueryClient
from spotapi.session import AccessToken, AuthSession
from spotapi.types import HTTPError, LoginExpired


@pytest.mark.parametrize(
    "timestamp,expected",
    [(59, "94287082"), (1111111109, "07081804"), (1111111111, "14050471")],
)
def test_totp_matches_rfc6238_sha1_vectors(timestamp: int, expected: str) -> None:
    assert generate_totp(b"12345678901234567890", timestamp=timestamp, digits=8) == expected


def test_totp_uses_latest_version_from_the_main_bundle_only() -> None:
    bundles = {
        "https://cdn.test/extra.js": 'secret:"ignored",version:99',
        "https://cdn.test/web-player.main.js": (
            'secret:"old",version:9;secret:"current",version:10'
        ),
    }
    assert extract_totp_secret(bundles) == ("current", 10)
    with pytest.raises(RuntimeError, match="TOTP secret"):
        extract_totp_secret({"https://cdn.test/extra.js": bundles["https://cdn.test/extra.js"]})


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
        authorized_headers={"authorization": "Bearer old", "client-token": "old-client"},
    )

    async def renew(*, previous_token: str | None = None) -> AccessToken:
        assert previous_token == "old"
        session.authorized_headers = {"authorization": "Bearer new", "client-token": "new-client"}
        return AccessToken("client", "new", 0, "new-client")

    session.refresh = AsyncMock(side_effect=renew)

    async with AsyncClient() as client:
        client._session = session
        headers = {"ACCEPT": "application/json"}
        if expected_calls == 1:
            with pytest.raises(HTTPError):
                await client.request(
                    method,
                    "https://spclient.wg.spotify.com/example",
                    authorized=True,
                    headers=headers,
                    retry_safe=retry_safe,
                )
        else:
            await client.request(
                method,
                "https://spclient.wg.spotify.com/example",
                authorized=True,
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

    with pytest.raises(LoginExpired, match="sp_dc"):
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
    client.transport.profile_user_agent = AsyncMock(return_value="Windows NT 10.0 Chrome/147.0")
    client.post = AsyncMock(
        return_value=Mock(json=ObjectDict({"granted_token": {"token": "synthetic-token"}}))
    )
    session = AuthSession(client)
    session.session = Mock(server_config=Mock(client_version="test"))
    assert await session._fetch_client_token("client-id") == "synthetic-token"
    client.post.assert_awaited_once()
    assert client.post.call_args.kwargs["retry_safe"] is True


async def test_client_token_uses_the_generated_user_agent_os() -> None:
    client = Mock(spec=AsyncClient)
    client.transport.profile_user_agent = AsyncMock(
        return_value="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) Chrome/147.0"
    )
    client.post = AsyncMock(
        return_value=Mock(json=ObjectDict({"granted_token": {"token": "synthetic-token"}}))
    )
    session = AuthSession(client)
    session.session = Mock(server_config=Mock(client_version="test"))

    assert await session._fetch_client_token("client-id") == "synthetic-token"

    device = client.post.call_args.kwargs["json"]["client_data"]["js_sdk_data"]
    assert (device["os"], device["os_version"]) == ("macOS", "10.15.7")


@pytest.mark.parametrize("status", [400, 401, 403, 429, 503])
async def test_login_error_only_classifies_rejected_authenticated_token_requests(
    status: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    client = Mock(spec=AsyncClient)
    original = HTTPError("Token rejected", status_code=status)
    client.get = AsyncMock(side_effect=original)
    session = AuthSession(client)
    session._require_user = True
    session.session = Mock(bundles={})
    monkeypatch.setattr("spotapi.session.build_totp", Mock(return_value=(1, "123456")))

    with pytest.raises(HTTPError) as raised:
        await session._fetch_access_token()

    assert isinstance(raised.value, LoginExpired) is (status == 401)
    assert raised.value.status_code == status
    if status == 401:
        assert raised.value.__cause__ is original
    else:
        assert raised.value is original


@pytest.mark.parametrize("status", [401, 403, 503])
async def test_login_bootstrap_only_classifies_an_unauthorized_session(
    status: int, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = AuthSession(Mock(spec=AsyncClient))
    session._require_user = True
    session.session = Mock(
        warm=AsyncMock(side_effect=HTTPError("Bootstrap failed", status_code=status))
    )
    monkeypatch.setattr(AuthSession, "resolve_user_agent", AsyncMock())

    with pytest.raises(HTTPError) as raised:
        await session.authorize()

    assert isinstance(raised.value, LoginExpired) is (status == 401)
    assert raised.value.status_code == status


@pytest.mark.parametrize("client_factory", [False, True])
async def test_login_rejection_is_preserved_when_failed_login_cleanup_also_fails(
    client_factory: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    rejected = LoginExpired("Log in again", status_code=401)
    client = Mock(
        spec=AsyncClient, close=AsyncMock(side_effect=ConnectionError("cleanup offline"))
    )
    monkeypatch.setattr(AuthSession, "authorize", AsyncMock(side_effect=rejected))
    monkeypatch.setattr(AsyncClient, "new", AsyncMock(return_value=client))

    with pytest.raises(LoginExpired) as caught:
        if client_factory:
            await AsyncClient.from_cookies("sp_dc=synthetic")
        else:
            await AuthSession.from_cookies("sp_dc=synthetic", client=client)

    assert caught.value is rejected
    assert caught.value.status_code == 401
    assert isinstance(caught.value.__cause__, ConnectionError)
    assert client.close.await_count >= 1
