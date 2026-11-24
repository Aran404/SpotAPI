"""Exercise saved credentials and browser ownership without a real Spotify login."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest

from spotapi import AsyncClient, SavedSession, browser_login
from spotapi.models.sessions import SessionInfo
from spotapi.types import BaseClientError, HTTPError


@pytest.fixture
def keyring(monkeypatch: pytest.MonkeyPatch) -> Mock:
    backend = Mock(get_password=Mock(return_value=None))
    monkeypatch.setattr(SavedSession, "_backend", Mock(return_value=backend))
    return backend


@pytest.fixture
def browser(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    browser = MagicMock()
    browser.close = AsyncMock()
    page = Mock(is_closed=Mock(return_value=False), goto=AsyncMock())
    context = Mock(
        new_page=AsyncMock(return_value=page),
        cookies=AsyncMock(return_value=[{"name": "sp_dc", "value": "synthetic-cookie"}]),
    )
    browser.new_context = AsyncMock(return_value=context)
    playwright = Mock(chromium=Mock(launch=AsyncMock(return_value=browser)))
    manager = MagicMock()
    manager.__aenter__ = AsyncMock(return_value=playwright)
    manager.__aexit__ = AsyncMock(return_value=False)
    sdk = Mock(async_playwright=Mock(return_value=manager))
    monkeypatch.setattr("spotapi.login.importlib.import_module", Mock(return_value=sdk))
    return browser


@pytest.fixture
def authorize(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    login = AsyncMock(return_value=Mock(spec=AsyncClient))
    monkeypatch.setattr(AsyncClient, "from_cookies", login)
    return login


@pytest.mark.parametrize("name", ["", "   "])
def test_session_requires_name(name: str) -> None:
    with pytest.raises(ValueError, match="session name"):
        SavedSession(name)


@pytest.mark.parametrize("cookie", ["", "value; extra", "value\r", "value\n"])
def test_session_rejects_invalid_cookie(keyring: Mock, cookie: str) -> None:
    with pytest.raises(ValueError, match="raw"):
        SavedSession().save(cookie)
    keyring.set_password.assert_not_called()


def test_missing_keyring_is_actionable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spotapi.login.importlib.import_module", Mock(side_effect=ImportError))
    with pytest.raises(RuntimeError, match=r"spotapi\[keyring\]"):
        SavedSession().info()


async def test_absent_session(keyring: Mock, authorize: AsyncMock) -> None:
    saved = SavedSession("work")
    assert saved.info() == SessionInfo("work", False)
    saved.clear()
    keyring.delete_password.assert_not_called()
    with pytest.raises(BaseClientError, match="No saved"):
        await saved.open()
    authorize.assert_not_awaited()


async def test_saved_session_reuses_cookie(keyring: Mock, authorize: AsyncMock) -> None:
    keyring.get_password.return_value = "saved-cookie"
    saved = SavedSession("work")
    assert await saved.open(language="fr-CA") is authorize.return_value
    authorize.assert_awaited_once_with("sp_dc=saved-cookie", language="fr-CA")
    authorize.reset_mock()

    assert await browser_login(saved=saved) is authorize.return_value
    authorize.assert_awaited_once_with("sp_dc=saved-cookie")
    keyring.set_password.assert_not_called()


@pytest.mark.parametrize("timeout", [False, 0, -1, float("inf"), float("nan")])
async def test_browser_rejects_invalid_timeout(timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        await browser_login(timeout=timeout)


async def test_browser_requires_optional_dependency(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spotapi.login.importlib.import_module", Mock(side_effect=ImportError))
    with pytest.raises(RuntimeError, match=r"spotapi\[browser\]"):
        await browser_login()


async def test_browser_login_without_persistence(browser: MagicMock, authorize: AsyncMock) -> None:
    assert await browser_login() is authorize.return_value
    authorize.assert_awaited_once_with("sp_dc=synthetic-cookie")
    browser.close.assert_awaited_once()


@pytest.mark.parametrize("force", [False, True])
async def test_browser_replaces_saved_cookie_only_after_authorization(
    keyring: Mock, browser: MagicMock, authorize: AsyncMock, force: bool
) -> None:
    keyring.get_password.return_value = "old-cookie"
    if not force:
        authorize.side_effect = [HTTPError("expired", status_code=401), authorize.return_value]

    assert await browser_login(saved=SavedSession("work"), force=force) is authorize.return_value
    assert authorize.await_count == (1 if force else 2)
    keyring.set_password.assert_called_once_with("spotapi", "work", "synthetic-cookie")
    browser.close.assert_awaited_once()


async def test_transient_saved_session_error_does_not_open_browser(
    keyring: Mock, authorize: AsyncMock
) -> None:
    keyring.get_password.return_value = "old-cookie"
    error = HTTPError("temporarily unavailable", status_code=503)
    authorize.side_effect = error
    with pytest.raises(HTTPError) as raised:
        await browser_login(saved=SavedSession())
    assert raised.value is error
    keyring.set_password.assert_not_called()


async def test_closed_login_window(
    browser: MagicMock, keyring: Mock, authorize: AsyncMock
) -> None:
    browser.new_context.return_value.new_page.return_value.is_closed.return_value = True
    with pytest.raises(BaseClientError, match="closed"):
        await browser_login(saved=SavedSession())
    browser.close.assert_awaited_once()
    authorize.assert_not_awaited()
    keyring.set_password.assert_not_called()


async def test_navigation_counts_toward_timeout(browser: MagicMock, authorize: AsyncMock) -> None:
    async def stall(*args: object) -> None:
        await asyncio.sleep(10)

    browser.new_context.return_value.new_page.return_value.goto.side_effect = stall
    with pytest.raises(TimeoutError):
        await browser_login(timeout=0.01)
    browser.close.assert_awaited_once()
    authorize.assert_not_awaited()


async def test_cancelled_browser_login_closes_window(
    browser: MagicMock, authorize: AsyncMock
) -> None:
    entered = asyncio.Event()

    async def wait(*args: object) -> None:
        entered.set()
        await asyncio.Future[None]()

    browser.new_context.return_value.new_page.return_value.goto.side_effect = wait
    task = asyncio.create_task(browser_login())
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    browser.close.assert_awaited_once()
    authorize.assert_not_awaited()


async def test_failed_authorization_does_not_replace_saved_cookie(
    browser: MagicMock, keyring: Mock, authorize: AsyncMock
) -> None:
    authorize.side_effect = HTTPError("rejected", status_code=401)
    with pytest.raises(HTTPError):
        await browser_login(saved=SavedSession())
    keyring.set_password.assert_not_called()
    browser.close.assert_awaited_once()


@pytest.mark.parametrize("cleanup_fails", [False, True])
async def test_failed_persistence_closes_client_and_preserves_error(
    browser: MagicMock, keyring: Mock, authorize: AsyncMock, cleanup_fails: bool
) -> None:
    error = OSError("credential store unavailable")
    keyring.set_password.side_effect = error
    client = authorize.return_value
    client.close = AsyncMock(side_effect=RuntimeError("cleanup") if cleanup_fails else None)
    with pytest.raises(OSError) as raised:
        await browser_login(saved=SavedSession())
    assert raised.value is error
    client.close.assert_awaited_once()
