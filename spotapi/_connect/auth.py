"""Account selection for the interactive terminal, without UI dependencies."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from .commands import profile_name

if TYPE_CHECKING:
    from spotapi.client import AsyncClient


async def open_account(profile: str, *, force: bool) -> AsyncClient:
    """Load an explicit shell session or authorize a named OS-keyring profile.

    Fresh logins use an isolated browser context. Cookies are never written to
    the working directory, and --force ignores an existing shell credential.
    """
    profile_name(profile)
    if not force and profile == "default" and (cookie := os.getenv("SPOTIFY_COOKIE")):
        from spotapi import AsyncClient

        return await AsyncClient.from_cookies(cookie)

    from spotapi import SavedSession, browser_login

    return await browser_login(saved=SavedSession(profile), force=force)
