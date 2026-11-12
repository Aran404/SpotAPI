"""Regressions for HTTP validation and structured logger filtering."""

from io import StringIO
from unittest.mock import Mock

import pytest

from spotapi.client import AsyncClient, _extra_headers, _require_spotify_url, _validate
from spotapi.connection import HTTPClient, Response
from spotapi.connection.types import Methods
from spotapi.models.account import AccountProfile
from spotapi.models.catalogue.profile_attributes import Profile
from spotapi.models.notifications import Notification, NotificationPage
from spotapi.session import AuthSession
from spotapi.types import BaseClientError, HTTPError
from spotapi.types.logger import Level, StandardLogger


def test_json_validation_ignores_media_type_case() -> None:
    response = Response(
        status_code=Mock(as_int=Mock(return_value=200), is_success=Mock(return_value=True)),
        text="invalid JSON",
        url="https://example.com",
        headers={"content-type": "Application/JSON"},
        json=None,
    )

    with pytest.raises(HTTPError, match="JSON"):
        _validate(response)


@pytest.mark.parametrize(("status", "method"), [(200, "HEAD"), (204, "GET"), (205, "POST")])
def test_bodyless_http_responses_do_not_require_json(status: int, method: Methods) -> None:
    response = Response(
        Mock(as_int=Mock(return_value=status), is_success=Mock(return_value=True)),
        "",
        "https://api.spotify.com",
        {"content-type": "application/json"},
        None,
    )
    assert _validate(response, method=method) is response


def test_expected_success_status_does_not_disable_json_validation() -> None:
    response = Response(
        Mock(as_int=Mock(return_value=200), is_success=Mock(return_value=True)),
        "invalid",
        "https://api.spotify.com",
        {"content-type": "application/json"},
        None,
    )
    with pytest.raises(HTTPError):
        _validate(response, expected_statuses=(200,))


@pytest.mark.parametrize("header", ["authorization", "Authorization", "CLIENT-TOKEN"])
def test_managed_credentials_cannot_be_overridden(header: str) -> None:
    with pytest.raises(ValueError, match="overridden"):
        _extra_headers({header: "replacement"})


def test_extra_headers_are_copied_and_normalized() -> None:
    original = {"ACCEPT": "application/protobuf"}
    result = _extra_headers(original)
    assert result == {"accept": "application/protobuf"}
    assert original == {"ACCEPT": "application/protobuf"}


@pytest.mark.parametrize(
    "url",
    [
        "http://api.spotify.com",
        "https://spotify.com.evil.test",
        "https://user@api.spotify.com",
        "https://example.com",
    ],
)
def test_managed_authorization_rejects_untrusted_destinations(url: str) -> None:
    with pytest.raises(ValueError, match="HTTPS Spotify"):
        _require_spotify_url(url)


def test_direct_session_is_attached_to_exactly_one_client() -> None:
    client = AsyncClient()
    client._http = Mock(spec=HTTPClient)
    session = AuthSession(client)
    assert client.session is session
    with pytest.raises(RuntimeError, match="already"):
        AuthSession(client)


def test_catch_respects_the_loggers_minimum_level() -> None:
    stream = StringIO()
    logger = StandardLogger(min_level=Level.WARNING, stream=stream)

    with logger.catch(ValueError, level=Level.DEBUG, reraise=False):
        raise ValueError("filtered")

    assert stream.getvalue() == ""

    with logger.catch(ValueError, level=Level.ERROR, reraise=False):
        raise ValueError("visible")

    assert "visible" in stream.getvalue()
    assert "Traceback" in stream.getvalue()


def test_catch_preserves_the_original_exception() -> None:
    logger = StandardLogger(stream=StringIO())
    original = ValueError("original")

    with pytest.raises(ValueError) as raised, logger.catch(ValueError):
        raise original

    assert raised.value is original


@pytest.mark.parametrize("value", ["CA", [1], None, {"CA": True}])
def test_profile_rejects_options_that_are_not_string_lists(value: object) -> None:
    with pytest.raises(BaseClientError, match="available_countries"):
        AccountProfile.from_dict(
            {
                "profile": {"username": "listener", "email": "listener@example.com"},
                "options": {"available_countries": value},
            }
        )


@pytest.mark.parametrize("identifier", [None, 123, ""])
def test_notification_rejects_missing_or_invalid_identity(identifier: object) -> None:
    with pytest.raises(BaseClientError, match="notification"):
        Notification.from_dict({"id": identifier, "createdTimestamp": "2026-11-11T12:00:00Z"})


def test_notification_preserves_timestamp_and_optional_metadata() -> None:
    item = Notification.from_dict(
        {"id": "notice", "createdTimestamp": "2026-11-11T12:00:00Z", "isNew": True}
    )
    assert item.created_at.utcoffset() is not None
    assert item.uri is None and item.image_url is None
    assert item.is_new is True


def test_notification_page_rejects_invalid_cursor_values() -> None:
    with pytest.raises(BaseClientError, match="cursor"):
        NotificationPage.from_dict(
            {"notifications": [], "forwardCursor": {"unexpected": "object"}}
        )


def test_profile_attributes_accept_native_keys_and_missing_optional_fields() -> None:
    profile = Profile.from_dict(
        {
            "accountId": "account",
            "name": "Listener",
            "username": "listener",
            "uri": "spotify:user:listener",
        }
    )
    assert profile.account_id == "account"
    assert profile.avatar is None and profile.social_handle is None


@pytest.mark.parametrize("value", [None, 123, False])
def test_profile_attributes_reject_invalid_required_names(value: object) -> None:
    with pytest.raises(BaseClientError, match="profile attributes"):
        Profile.from_dict(
            {
                "accountId": "account",
                "name": value,
                "username": "listener",
                "uri": "spotify:user:listener",
            }
        )
