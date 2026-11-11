"""Exercise the real bundled frontend against a deterministic local bridge."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("playwright.async_api")
from playwright.async_api import Error, Page, async_playwright

from examples.studio.actions import manifest
from examples.studio.desktop import page

ARTIST = {"uri": "spotify:artist:artist", "profile": {"name": "Daft Punk"}}
ALBUM = {"uri": "spotify:album:album", "name": "Discovery"}
TRACK = {
    "name": "One More Time",
    "uri": "spotify:track:test",
    "id": "test",
    "artists": {"items": [ARTIST]},
    "album_of_track": ALBUM,
}


@pytest.fixture
async def studio_page() -> AsyncGenerator[tuple[Page, list[str]], None]:
    """Use an isolated headless browser, without accessing an existing browser profile."""
    async with async_playwright() as playwright:
        chrome = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
        try:
            browser = await playwright.chromium.launch(
                channel="chrome" if chrome.exists() else None
            )
        except Error as error:
            if "Executable doesn't exist" in str(error):
                pytest.skip(
                    "install the optional browser with python -m playwright install chromium"
                )
            raise
        context = await browser.new_context(viewport={"width": 1440, "height": 960})
        view = await context.new_page()
        requests: list[str] = []

        async def request(action: str, values: dict[str, str]) -> dict[str, Any]:
            requests.append(action)
            if action == "bootstrap":
                data: object = {"signed_in": True, "name": "Studio", "actions": manifest()}
            elif action == "search":
                data = {"tracks": [TRACK], "artists": [], "albums": [], "playlists": []}
            elif action == "top":
                data = {"tracks": [TRACK], "artists": []}
            elif action == "detail":
                match values.get("uri"):
                    case "spotify:artist:artist":
                        data = {
                            **ARTIST,
                            "discography": {"popular_releases_albums": {"items": [ALBUM]}},
                        }
                    case "spotify:album:album":
                        data = {
                            **ALBUM,
                            "artists": {"items": [ARTIST]},
                            "tracks_v2": {"items": [{"track": TRACK}]},
                        }
                    case _:
                        data = {
                            **TRACK,
                            "artists": None,
                            "first_artist": {"items": [ARTIST]},
                        }
            elif action == "player":
                data = {"state": None, "devices": [], "events": []}
            elif action == "lyrics":
                data = {
                    "provider": "LRCLIB",
                    "sync_type": "LINE_SYNCED",
                    "lines": [{"start_time_ms": 4000, "words": "A timed line"}],
                }
            else:
                data = {"completed": True}
            return {"ok": True, "data": data}

        await cast(Any, view).expose_function("studio_request", request)
        await view.set_content(page())
        await view.evaluate("""() => {
            window.pywebview = {api: {request: window.studio_request}};
            window.dispatchEvent(new Event('pywebviewready'));
        }""")
        await view.get_by_role("heading", name="One More Time", exact=True).wait_for()
        try:
            yield view, requests
        finally:
            await context.close()
            await browser.close()


async def test_discovery_detail_and_navigation_round_trip(
    studio_page: tuple[Page, list[str]],
) -> None:
    view, requests = studio_page
    await view.get_by_role("heading", name="One More Time", exact=True).click()
    await view.locator("#detail").wait_for(state="visible")
    await view.get_by_role("button", name="Close details").click()
    await view.get_by_role("button", name="Your rotation", exact=True).click()
    await view.get_by_role("button", name="Six months", exact=True).wait_for()
    await view.get_by_role("button", name="Discover", exact=True).click()
    await view.locator("#section-tools").get_by_role(
        "button", name="Audiobooks", exact=True
    ).wait_for()
    assert "top" in requests and "detail" in requests
    assert await view.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


async def test_lab_cancel_never_sends_an_account_mutation(
    studio_page: tuple[Page, list[str]],
) -> None:
    view, requests = studio_page
    await view.get_by_role("button", name="Feature lab API", exact=True).click()
    await view.get_by_role("button", name="Change password", exact=True).click()
    await view.get_by_label("current password", exact=True).fill("synthetic-current")
    await view.get_by_label("new password", exact=True).fill("synthetic-new")
    await view.get_by_role("button", name="Try it with SpotAPI", exact=True).click()
    await view.get_by_role("button", name="Keep things as they are", exact=True).click()
    assert "change_password" not in requests


async def test_detail_links_follow_artist_and_album_with_local_back_navigation(
    studio_page: tuple[Page, list[str]],
) -> None:
    view, requests = studio_page
    dialog = view.locator("#detail")
    await view.get_by_role("heading", name="One More Time", exact=True).click()
    artist = dialog.get_by_role("button", name="Daft Punk", exact=True)
    await artist.hover()
    assert await artist.evaluate("el => getComputedStyle(el).textDecorationLine") == "underline"
    await artist.press("Enter")
    await dialog.get_by_role("heading", name="Daft Punk", exact=True).wait_for()
    await dialog.get_by_role("button", name="Discovery", exact=True).click()
    await dialog.get_by_role("heading", name="Discovery", exact=True).wait_for()
    await dialog.get_by_role("heading", name="Tracks", exact=True).wait_for()

    before = requests.count("detail")
    await dialog.get_by_role("button", name="Back", exact=True).click()
    await dialog.get_by_role("heading", name="Daft Punk", exact=True).wait_for()
    await dialog.get_by_role("button", name="Back", exact=True).click()
    await dialog.get_by_role("heading", name="One More Time", exact=True).wait_for()
    assert await artist.evaluate("el => el === document.activeElement")
    assert requests.count("detail") == before == 3


async def test_compact_layout_has_no_horizontal_overflow(
    studio_page: tuple[Page, list[str]],
) -> None:
    view, _ = studio_page
    await view.set_viewport_size({"width": 980, "height": 720})
    assert await view.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    await view.get_by_role("button", name="Feature lab API", exact=True).click()
    assert await view.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


async def test_timed_lyrics_only_seek_the_matching_track(
    studio_page: tuple[Page, list[str]],
) -> None:
    view, requests = studio_page
    await view.get_by_role("heading", name="One More Time", exact=True).click()
    dialog = view.locator("#detail")
    await dialog.get_by_role("button", name="Lyrics", exact=True).click()
    line = dialog.get_by_role("button", name="A timed line")
    await line.wait_for()
    assert await line.is_disabled()
    await view.evaluate("""() => {
        const request = window.pywebview.api.request;
        window.pywebview.api.request = (action, values) => {
            if (action === 'seek') window.lastSeek = values;
            return request(action, values);
        };
        updatePlayer({state: {track: {uri: 'spotify:track:test'}, position: 4000}});
    }""")
    await line.press("Enter")
    await view.wait_for_function("Boolean(window.lastSeek)")
    assert await view.evaluate("window.lastSeek") == {
        "uri": "spotify:track:test",
        "position_ms": "4000",
        "confirmed": "true",
    }
    assert "seek" in requests


async def test_closing_details_discards_a_pending_related_view(
    studio_page: tuple[Page, list[str]],
) -> None:
    view, _ = studio_page
    await view.get_by_role("heading", name="One More Time", exact=True).click()
    await view.locator("#detail").get_by_role("heading", name="One More Time").wait_for()
    await view.evaluate("""() => {
        const request = window.pywebview.api.request;
        window.pywebview.api.request = (action, values) =>
            action === 'detail' && values.uri === 'spotify:artist:artist'
                ? new Promise(resolve => { window.resolveArtist = resolve; })
                : request(action, values);
        window.pendingArtist = inspect('spotify:artist:artist');
    }""")
    await view.get_by_role("button", name="Close details").click()
    await view.evaluate("""async () => {
        window.resolveArtist({ok: true, data: {name: 'Late artist'}});
        await window.pendingArtist;
    }""")
    assert not await view.locator("#detail").evaluate("dialog => dialog.open")


async def test_account_switch_discards_pending_details_and_player_responses(
    studio_page: tuple[Page, list[str]],
) -> None:
    view, _ = studio_page
    await view.wait_for_function("!state.polling")
    await view.evaluate("""() => {
        window.delayed = {};
        window.pywebview.api.request = (action) => {
            if (action === 'detail' || action === 'player')
                return new Promise(resolve => window.delayed[action] = resolve);
            if (action === 'bootstrap')
                return Promise.resolve({ok: true, data: {signed_in: true, name: 'New account', actions: []}});
            return Promise.resolve({ok: true, data: {tracks: []}});
        };
        window.oldDetail = inspect('spotify:track:old');
        window.oldPlayer = pollPlayer();
    }""")
    await view.wait_for_function("Boolean(window.delayed.detail && window.delayed.player)")
    await view.evaluate("window.studio.signedIn()")
    await view.evaluate("""async () => {
        window.delayed.detail({ok: true, data: {name: 'Previous account detail', uri: 'spotify:track:old'}});
        window.delayed.player({ok: true, data: {state: {track: {name: 'Previous account track'}}}});
        await Promise.all([window.oldDetail, window.oldPlayer]);
    }""")
    assert not await view.locator("#detail").evaluate("dialog => dialog.open")
    assert "Previous account" not in await view.locator("body").inner_text()
    assert await view.locator("#now-name").inner_text() == "No active track"
