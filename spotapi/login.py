"""Optional interactive login and OS-keyring session persistence."""

from __future__ import annotations

import asyncio
import importlib
import math
from typing import Any

from .client import AsyncClient
from .models.sessions import SessionInfo
from .types import BaseClientError, HTTPError


class SavedSession:
    """Persist an sp_dc cookie in the operating system's credential store.

    Requires ``spotapi[keyring]`` and a supported backend. No plaintext-file
    fallback is used. This object never includes the cookie in repr or info().
    Saving does not validate the session; open() authorizes it with Spotify.
    """

    __slots__ = ("name",)

    def __init__(self, name: str = "default") -> None:
        if not name.strip():
            raise ValueError("A session name is required")
        self.name = name

    def _backend(self) -> Any:
        try:
            return importlib.import_module("keyring")
        except ImportError as error:
            raise RuntimeError(
                "Install saved sessions with pip install 'spotapi[keyring]'"
            ) from error

    def _cookie(self) -> str | None:
        cookie = self._backend().get_password("spotapi", self.name)
        return cookie if isinstance(cookie, str) and cookie else None

    def save(self, cookie: str) -> None:
        """Store the raw sp_dc value; backend failures propagate without a file fallback."""
        if not cookie or any(char in cookie for char in "\r\n;"):
            raise ValueError("Supply the raw, nonempty sp_dc cookie value")
        self._backend().set_password("spotapi", self.name, cookie)

    def info(self) -> SessionInfo:
        """Check presence without returning credentials or claiming validity."""
        return SessionInfo(self.name, self._cookie() is not None)

    def clear(self) -> None:
        """Remove this named credential if present."""
        if self._cookie() is not None:
            self._backend().delete_password("spotapi", self.name)

    async def open(self, **options: Any) -> AsyncClient:
        """Authorize a new managed client from the saved cookie, without a browser."""
        cookie = await asyncio.to_thread(self._cookie)
        if cookie is None:
            raise BaseClientError("No saved Spotify session exists under this name")
        return await AsyncClient.from_cookies(f"sp_dc={cookie}", **options)


async def browser_login(*, saved: SavedSession | None = None, timeout: float = 180) -> AsyncClient:
    """Open Spotify's login in a browser and return an authorized managed client.

    Requires ``spotapi[browser]`` and a Playwright Chromium installation. The
    user completes login; SpotAPI does not request or store a password. Only
    the captured Spotify sp_dc cookie is retained, and only when saved is
    explicitly supplied. Reuse a valid saved session before opening a browser.
    Close the returned client after use. Closing the browser or timeout aborts.
    """
    if isinstance(timeout, bool) or not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("timeout must be positive")
    if saved is not None and (await asyncio.to_thread(saved.info)).present:
        try:
            return await saved.open()
        except HTTPError as error:
            if error.status_code not in {401, 403}:
                raise
    try:
        module: Any = importlib.import_module("playwright.async_api")
    except ImportError as error:
        raise RuntimeError(
            "Install browser login with pip install 'spotapi[browser]' and playwright install chromium"
        ) from error
    async with module.async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        try:
            context = await browser.new_context()
            page = await context.new_page()
            await page.goto(
                "https://accounts.spotify.com/login?continue=https%3A%2F%2Fopen.spotify.com%2F"
            )
            async with asyncio.timeout(timeout):
                while True:
                    if page.is_closed():
                        raise BaseClientError("Spotify login window was closed")
                    cookies: list[dict[str, Any]] = await context.cookies(
                        "https://open.spotify.com"
                    )
                    cookie = next(
                        (
                            item["value"]
                            for item in cookies
                            if item.get("name") == "sp_dc" and item.get("value")
                        ),
                        None,
                    )
                    if isinstance(cookie, str):
                        break
                    await asyncio.sleep(0.25)
        finally:
            await browser.close()
    client = await AsyncClient.from_cookies(f"sp_dc={cookie}")
    try:
        if saved is not None:
            await asyncio.to_thread(saved.save, cookie)
    except BaseException:
        await client.close()
        raise
    return client
