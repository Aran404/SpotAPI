"""Check the desktop service against real Spotify without mutating account data."""

import os

import pytest

from spotapi._studio.service import Studio

pytestmark = [pytest.mark.live, pytest.mark.authenticated]


async def test_live_studio_authenticated_views_and_public_dispatch() -> None:
    """Exercise the GUI's real typed backend, separate from browser fixtures."""
    studio = Studio()
    try:
        await studio.authenticate(os.environ["SPOTIFY_COOKIE"])
        for action in (
            "bootstrap",
            "library",
            "liked",
            "top",
            "notifications",
            "notifications_unread",
            "account",
            "plan",
            "verify",
            "player",
            "recents",
        ):
            result = await studio.request(action, {})
            assert result["ok"], (action, result.get("error"))

        for action, values in (
            ("search", {"query": "Daft Punk"}),
            ("detail", {"uri": "spotify:track:33XUHrCbrAW6me9ewdCZip"}),
            ("credits", {"uri": "spotify:track:33XUHrCbrAW6me9ewdCZip"}),
            ("radio", {"uri": "spotify:track:33XUHrCbrAW6me9ewdCZip"}),
            ("recommendations", {"uri": "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"}),
            ("profile", {"user": "spotify"}),
            ("profile_playlists", {"user": "spotify"}),
        ):
            result = await studio.request(action, values)
            assert result["ok"], (action, result.get("error"))
    finally:
        await studio.close()
