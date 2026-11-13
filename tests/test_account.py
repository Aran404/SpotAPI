"""Account settings, CSRF rotation and provider-neutral CAPTCHA contracts."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import Account, AsyncClient, CaptchaRequired, CaptchaSolver, PasswordReset, Private
from spotapi.account_session import AccountPage, AccountSession
from spotapi.connection import Response
from spotapi.datastruct import ObjectDict
from spotapi.models import AccountChallenge
from spotapi.session import AuthSession
from spotapi.types import BaseClientError, HTTPError


def response(
    body: Mapping[str, Any] | None = None,
    *,
    status: int = 200,
    headers: Mapping[str, str] | None = None,
    text: str = "",
) -> Mock:
    return Mock(
        spec=Response,
        json=ObjectDict(body) if body is not None else None,
        headers=dict(headers or {}),
        text=text,
        ok=200 <= status < 300,
        status_code=Mock(as_int=Mock(return_value=status)),
    )


def profile_body() -> dict[str, Any]:
    return {
        "profile": {
            "username": "listener",
            "email": "listener@example.test",
            "birthdate": "2000-06-01",
            "country": "CA",
            "gender": "MALE",
            "third_party_email": True,
        },
        "options": {
            "editable_fields": ["email", "birthdate", "country", "gender", "third_party_email"],
            "available_countries": ["CA", "EG"],
            "available_genders": ["MALE", "FEMALE", "NOT_SPECIFIED"],
            "is_password_required_on_email_change": False,
        },
    }


@pytest.fixture
def session() -> Mock:
    client = Mock(spec=AsyncClient)
    client.transport.request = AsyncMock(
        return_value=response(profile_body(), headers={"x-csrf-token": "profile-token"})
    )
    client.get = AsyncMock(return_value=response(text='<body data-csrf="page-token"></body>'))
    return Mock(spec=AuthSession, client=client)


def test_account_page_reads_csrf_attribute_and_next_data() -> None:
    page = AccountPage(
        '<body data-csrf="attribute-token"><script id="__NEXT_DATA__" type="application/json">'
        '{"props":{"csrfToken":"json-token"}}</script><script>ignored()</script></body>'
    )
    assert page.csrf == "attribute-token"
    assert page.data["props"]["csrfToken"] == "json-token"


async def test_private_scope_forwards_connection_options_and_exits_on_cancellation(
    monkeypatch: pytest.MonkeyPatch, session: Mock
) -> None:
    client = session.client
    client.session = session
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    factory = AsyncMock(return_value=client)
    monkeypatch.setattr(AsyncClient, "from_cookies", factory)

    with pytest.raises(asyncio.CancelledError):
        async with Private.from_cookies(
            "sp_dc=synthetic", proxy="http://proxy.test:8080", language="fr"
        ) as account:
            assert account.session is session
            raise asyncio.CancelledError()

    factory.assert_awaited_once_with(
        "sp_dc=synthetic", proxy="http://proxy.test:8080", language="fr"
    )
    client.__aexit__.assert_awaited_once()
    assert client.__aexit__.await_args is not None
    assert client.__aexit__.await_args.args[0] is asyncio.CancelledError


async def test_plan_rotation_is_used_by_the_next_profile_request(session: Mock) -> None:
    page = {
        "props": {
            "csrfToken": "rotated-token",
            "pageProps": {
                "dynamicWidgets": {
                    "PlanCard": [
                        {"props": {"planName": "Premium Duo", "description": "Two accounts"}}
                    ]
                }
            },
        }
    }
    session.client.get.return_value = response(
        text='<script id="__NEXT_DATA__">' + json.dumps(page) + "</script>"
    )
    session.client.transport.request.side_effect = [
        response(profile_body(), headers={"x-csrf-token": "old-token"}),
        response({"validation_errors": []}),
    ]
    account = Account(session)
    profile = await account.get_profile()
    plan = await account.get_plan()
    errors = await account.validate_profile(gender="MALE")

    assert profile.birthdate == date(2000, 6, 1)
    assert profile.email not in repr(profile)
    assert plan.is_premium is True and not errors
    calls = session.client.transport.request.await_args_list
    assert "json" not in calls[0].kwargs
    assert calls[1].kwargs["headers"]["x-csrf-token"] == "rotated-token"
    assert calls[1].kwargs["json"] == {"profile": {"gender": "MALE"}}


@pytest.mark.parametrize("status", [400, 401, 403])
async def test_csrf_refusal_can_retry_once_with_a_changed_response_token(
    session: Mock, status: int
) -> None:
    http = AccountSession(session.client, "https://accounts.spotify.com/en/password-reset")
    http.csrf = "stale"
    session.client.transport.request.side_effect = [
        response(status=status, headers={"x-csrf-token": "fresh"}),
        response(status=204),
    ]
    await http.request("POST", "/api/password/recovery", body={"captcha": "manual-token"})

    calls = session.client.transport.request.await_args_list
    assert len(calls) == 2
    assert [call.kwargs["headers"]["x-csrf-token"] for call in calls] == ["stale", "fresh"]
    assert all(call.kwargs["max_attempts"] == 1 for call in calls)


@pytest.mark.parametrize("status", [401, 429, 500])
async def test_account_failure_without_csrf_rotation_never_replays(
    session: Mock, status: int
) -> None:
    http = AccountSession(session.client, "https://www.spotify.com/account/profile/")
    http.csrf = "unchanged"
    rejected = response(status=status)
    session.client.transport.request.return_value = rejected

    with pytest.raises(HTTPError) as caught:
        await http.request("PUT", "/api/account-settings/v2/profile", body={"profile": {}})

    assert caught.value.status_code == status and caught.value.response is rejected
    assert session.client.transport.request.await_count == 1


async def test_profile_update_preserves_omitted_fields_and_false_values(session: Mock) -> None:
    updated = profile_body()
    updated["profile"]["third_party_email"] = False
    session.client.transport.request.side_effect = [
        response(profile_body(), headers={"x-csrf-token": "csrf"}),
        response({"user_profile_response": updated}),
    ]
    account = Account(session)
    result = await account.edit_profile(third_party_email=False, token="captcha")

    assert result is account.profile and not isinstance(result, AccountChallenge)
    assert result.third_party_email is False
    sent = session.client.transport.request.await_args_list[-1].kwargs["json"]
    assert sent["profile"] == {
        key: value for key, value in updated["profile"].items() if key != "username"
    }
    assert sent["profile"]["birthdate"] == "2000-06-01"
    assert sent["profile"]["third_party_email"] is False
    assert sent["client_nonce"] == account.client_nonce
    assert sent["recaptcha_token"] == "captcha"


async def test_missing_captcha_is_an_explicit_typed_request(session: Mock) -> None:
    with pytest.raises(CaptchaRequired) as caught:
        await Account(session).edit_profile(gender="NOT_SPECIFIED")

    assert caught.value.challenge.action == "account_settings/profile_update"
    assert caught.value.challenge.enterprise is True
    assert session.client.transport.request.await_count == 1


async def test_async_solver_and_account_challenge_are_returned_without_redirecting(
    session: Mock,
) -> None:
    solver = Mock(spec=CaptchaSolver, solve=AsyncMock(return_value="solved"))
    session.client.transport.request.side_effect = [
        response(profile_body(), headers={"x-csrf-token": "csrf"}),
        response(
            {
                "challenge_response": {
                    "challenge_url": "https://accounts.spotify.com/challenge",
                    "session_id": "session",
                    "server_nonce": "secret-nonce",
                }
            }
        ),
    ]
    account = Account(session, solver=solver)
    result = await account.edit_profile(gender="NOT_SPECIFIED")

    assert isinstance(result, AccountChallenge)
    assert result.url == "https://accounts.spotify.com/challenge"
    assert "secret-nonce" not in repr(result)
    solver.solve.assert_awaited_once()
    assert account.profile is not None and account.profile.gender == "MALE"


async def test_invalid_profile_option_fails_before_captcha_or_mutation(session: Mock) -> None:
    solver = Mock(spec=CaptchaSolver, solve=AsyncMock())
    with pytest.raises(ValueError, match="country"):
        await Account(session, solver=solver).edit_profile(country="ZZ")

    solver.solve.assert_not_awaited()
    assert session.client.transport.request.await_count == 1


def test_nonce_matches_two_unsigned_browser_words(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    words = iter([4294967295, 7])

    def word(bits: int) -> int:
        assert bits == 32
        return next(words)

    monkeypatch.setattr("spotapi.account.secrets.randbits", word)
    assert Account(session).client_nonce == "42949672957"


async def test_password_recovery_uses_the_current_csrf_and_captcha_contract(session: Mock) -> None:
    reset = PasswordReset(session.client)
    session.client.transport.request.return_value = response(status=204)
    await reset.request("listener", token="captcha")

    sent = session.client.transport.request.await_args_list[0]
    assert sent.args == ("POST", "https://accounts.spotify.com/api/password/recovery")
    assert sent.kwargs["json"]["emailOrUsername"] == "listener"
    assert sent.kwargs["json"]["flowId"] == reset.flow_id
    assert sent.kwargs["json"]["captcha"] == "captcha"
    assert sent.kwargs["headers"]["x-csrf-token"] == "page-token"


async def test_password_change_is_one_request_with_no_captcha_dependency(session: Mock) -> None:
    session.client.transport.request.return_value = response(status=204)
    await Account(session).change_password("old-password", "new-password")

    sent = session.client.transport.request.await_args_list[0]
    assert sent.args[1].endswith("/api/account-settings/v1/change-password")
    assert sent.kwargs["json"] == {"old_password": "old-password", "new_password": "new-password"}
    assert sent.kwargs["max_attempts"] == 1


async def test_legacy_plan_error_html_is_not_a_subscription(session: Mock) -> None:
    session.client.get.return_value = response(text="<html>Not found</html>")
    with pytest.raises(BaseClientError):
        await Account(session).get_plan()
