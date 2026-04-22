# type: ignore
"""Unit tests for the hybrid token refresh flow in BaseClient / TLSClient.

These tests do not hit the network: the HTTP layer is patched so the
refresh/retry decision logic can be exercised in isolation.
"""
import time
from unittest.mock import MagicMock

import pytest

from spotapi.client import BaseClient
from spotapi.http.data import Response
from spotapi.http.request import TLSClient
from spotapi.types.alias import _Undefined


def _make_base():
    """A BaseClient whose init-time network methods are stubbed out."""
    client = TLSClient("chrome_120", "", auto_retries=1)
    base = BaseClient(client=client)
    # Pre-populate so _auth_rule does not fall into the first-time init branches
    base.client_token = "ct"
    base.access_token = "at"
    base.client_id = "cid"
    base.client_version = "1.0.0"
    base.device_id = "did"
    base.access_token_expires_at_ms = (time.time() + 600) * 1000  # 10 min out
    return base


def _make_tls_response(status_code, headers=None, text=""):
    mock = MagicMock()
    mock.status_code = status_code
    mock.headers = headers or {}
    mock.text = text
    mock.url = "https://example.com/x"
    mock.json.return_value = None
    return mock


def _make_response(status_code, headers=None):
    raw = _make_tls_response(status_code, headers=headers)
    return Response(raw=raw, status_code=status_code, response=None)


# ---------- _auth_rule proactive refresh ----------


def test_proactive_refresh_fires_when_near_expiry():
    base = _make_base()
    base.access_token_expires_at_ms = (time.time() + 1) * 1000  # inside skew window
    calls = []
    base._get_auth_vars = lambda: calls.append("called")

    base._auth_rule({})

    assert calls == ["called"]


def test_proactive_refresh_skipped_when_fresh():
    base = _make_base()  # expiry is 10 min out
    calls = []
    base._get_auth_vars = lambda: calls.append("called")

    base._auth_rule({})

    assert calls == []


def test_auth_rule_sets_expected_headers():
    base = _make_base()
    kwargs = base._auth_rule({})

    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer at"
    assert headers["Client-Token"] == "ct"
    assert headers["Spotify-App-Version"] == "1.0.0"


# ---------- _handle_auth_failure ----------


def test_handle_401_refreshes_access_token():
    base = _make_base()
    calls = []

    def fake_refresh():
        calls.append("called")
        base.access_token = "new_at"

    base._get_auth_vars = fake_refresh
    base.access_token = _Undefined  # simulate reset-before-refresh

    retried = base._handle_auth_failure(_make_response(401))

    assert retried is True
    assert calls == ["called"]


def test_handle_401_resets_access_token_before_refresh():
    base = _make_base()
    seen = []
    base._get_auth_vars = lambda: seen.append(base.access_token)

    base._handle_auth_failure(_make_response(401))

    assert seen == [_Undefined], "access_token must be reset before _get_auth_vars runs"


def test_handle_400_with_client_token_error_refreshes_client_token():
    base = _make_base()
    calls = []

    def fake_refresh():
        calls.append("called")
        base.client_token = "new_ct"

    base.get_client_token = fake_refresh

    retried = base._handle_auth_failure(
        _make_response(400, headers={"Client-Token-Error": "INVALID_CLIENTTOKEN"})
    )

    assert retried is True
    assert calls == ["called"]


def test_handle_400_without_client_token_error_returns_false():
    base = _make_base()
    base.get_client_token = lambda: pytest.fail("should not refresh")
    base._get_auth_vars = lambda: pytest.fail("should not refresh")

    retried = base._handle_auth_failure(_make_response(400))

    assert retried is False


def test_handle_500_returns_false():
    base = _make_base()
    base.get_client_token = lambda: pytest.fail("should not refresh")
    base._get_auth_vars = lambda: pytest.fail("should not refresh")

    retried = base._handle_auth_failure(_make_response(500))

    assert retried is False


def test_handle_200_returns_false():
    base = _make_base()
    retried = base._handle_auth_failure(_make_response(200))
    assert retried is False


# ---------- TLSClient._send retry-once ----------


def _patch_send(client, responses):
    """Make build_request return the given TLS responses in sequence."""
    it = iter(responses)
    client.build_request = lambda *args, **kwargs: next(it)


def test_send_retries_once_on_auth_failure():
    client = TLSClient("chrome_120", "", auto_retries=1)
    _patch_send(
        client,
        [
            _make_tls_response(401, headers={"Www-Authenticate": "Bearer"}),
            _make_tls_response(200),
        ],
    )

    auth_calls = []
    client.authenticate = lambda kwargs: (auth_calls.append(1) or kwargs)
    client.on_auth_failure = lambda resp: True

    resp = client.get("https://example.com/x", authenticate=True)

    assert resp.status_code == 200
    assert len(auth_calls) == 2, "authenticate should run once per attempt"


def test_send_does_not_retry_when_handler_returns_false():
    client = TLSClient("chrome_120", "", auto_retries=1)
    _patch_send(client, [_make_tls_response(500)])

    client.authenticate = lambda kwargs: kwargs
    client.on_auth_failure = lambda resp: False

    resp = client.get("https://example.com/x", authenticate=True)

    assert resp.status_code == 500


def test_send_does_not_retry_without_authenticate_flag():
    client = TLSClient("chrome_120", "", auto_retries=1)
    _patch_send(client, [_make_tls_response(401)])

    client.authenticate = lambda kwargs: kwargs
    client.on_auth_failure = lambda resp: pytest.fail("should not be called")

    resp = client.get("https://example.com/x", authenticate=False)

    assert resp.status_code == 401


def test_send_retries_at_most_once_even_if_second_attempt_also_fails():
    client = TLSClient("chrome_120", "", auto_retries=1)
    # If _send retried more than once, StopIteration would fire
    _patch_send(
        client,
        [_make_tls_response(401), _make_tls_response(401)],
    )

    client.authenticate = lambda kwargs: kwargs
    handler_calls = []
    client.on_auth_failure = lambda resp: (handler_calls.append(1) or True)

    resp = client.get("https://example.com/x", authenticate=True)

    assert resp.status_code == 401
    assert len(handler_calls) == 1, "on_auth_failure must only be consulted once"
