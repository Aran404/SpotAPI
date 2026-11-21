"""Desktop ownership, bridge isolation and request dispatch without a GUI dependency."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator
from http.cookies import SimpleCookie
from unittest.mock import AsyncMock, Mock

import pytest

from spotapi import AsyncClient, Catalogue, Player
from spotapi._studio.actions import ACTIONS
from spotapi._studio.desktop import Bridge, _authenticate, page
from spotapi._studio.lyrics import _studio_user_agent, parse_lyrics
from spotapi._studio.service import Studio, first_page, serialize
from spotapi.models import AccountChallenge


def test_window_creation_failure_closes_the_unstarted_loop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spotapi._studio import desktop

    loop = asyncio.new_event_loop()
    backend = Mock()
    backend.create_window.side_effect = RuntimeError("Native window unavailable")
    monkeypatch.setattr("dotenv.load_dotenv", Mock())
    monkeypatch.setattr(desktop, "import_module", Mock(return_value=backend))
    monkeypatch.setattr(desktop.asyncio, "new_event_loop", Mock(return_value=loop))
    worker = Mock()
    monkeypatch.setattr(desktop.threading, "Thread", Mock(return_value=worker))
    with pytest.raises(RuntimeError, match="Native window unavailable"):
        desktop.main()
    assert loop.is_closed()
    worker.start.assert_not_called()


def test_native_app_exit_closes_its_worker_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    from spotapi._studio import desktop

    loop = asyncio.new_event_loop()
    backend = Mock()

    def initialize(callback: object, **options: object) -> None:
        assert callable(callback)
        callback()

    backend.start.side_effect = initialize
    monkeypatch.setattr("dotenv.load_dotenv", Mock())
    monkeypatch.delenv("SPOTIFY_COOKIE", raising=False)
    monkeypatch.setattr(desktop, "import_module", Mock(return_value=backend))
    monkeypatch.setattr(desktop.asyncio, "new_event_loop", Mock(return_value=loop))
    desktop.main()
    assert loop.is_closed()
    backend.start.assert_called_once()


def test_public_lyrics_distinguish_timed_lines_from_plain_text() -> None:
    synced = parse_lyrics({"syncedLyrics": "[00:05.1][00:01.030] A line\n[ar:Artist]"})
    assert synced is not None and synced.sync_type == "LINE_SYNCED"
    assert [line.start_time_ms for line in synced.lines] == [1030, 5100]

    plain = parse_lyrics({"plainLyrics": "First line\nSecond line"})
    assert plain is not None and plain.sync_type == "UNSYNCED"
    assert [line.words for line in plain.lines] == ["First line", "Second line"]
    assert parse_lyrics({"instrumental": True}) is None


async def test_studio_opens_catalogue_once_and_closes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    enter = AsyncMock()
    search = AsyncMock(return_value={"tracks": []})
    close = AsyncMock()
    monkeypatch.setattr(Catalogue, "__aenter__", enter)
    monkeypatch.setattr(Catalogue, "search", search)
    monkeypatch.setattr(Catalogue, "close", close)
    studio = Studio()
    try:
        assert (await studio.request("search", {"query": "first"}))["ok"]
        assert (await studio.request("search", {"query": "second"}))["ok"]
        enter.assert_awaited_once()
        assert search.await_count == 2
        assert len(search.call_args.kwargs["types"]) == 10
    finally:
        await studio.close()
    close.assert_awaited_once()


async def test_studio_rejects_changes_without_confirmation_before_opening_a_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    enter = AsyncMock()
    monkeypatch.setattr(Catalogue, "__aenter__", enter)
    studio = Studio()
    result = await studio.request(
        "change_password", {"current_password": "private", "new_password": "also-private"}
    )
    assert result["ok"] is False and "Confirm" in result["error"]
    assert "private" not in result["error"]
    enter.assert_not_awaited()
    assert (await studio.request("not_a_real_method", {}))["ok"] is False


async def test_preview_closes_early_page_generators() -> None:
    closed = asyncio.Event()

    async def pages() -> AsyncGenerator[int, None]:
        try:
            yield 1
            yield 2
        finally:
            closed.set()

    assert await first_page(pages()) == 1
    assert closed.is_set()


async def test_studio_records_the_real_observer_state_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def start(self: Player, *, reconnect: bool = True) -> None:
        self.process_message(
            {"payloads": [{"cluster": {"timestamp": 1, "player_state": {"is_paused": True}}}]}
        )
        self._ready.set()
        await asyncio.Future[None]()

    monkeypatch.setattr(Player, "start", start)
    studio = Studio()
    studio.client = Mock(spec=AsyncClient, close=AsyncMock())
    try:
        await studio._connect_player()
        await asyncio.sleep(0)
        assert len(studio.events) == 1
        assert studio.events[0]["event"] == "state"
        assert studio.events[0]["data"]["paused"] is True
    finally:
        await studio.close()


async def test_studio_closes_http_even_when_catalogue_cleanup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close = AsyncMock(side_effect=RuntimeError("catalogue cleanup failed"))
    monkeypatch.setattr(Catalogue, "close", close)
    studio = Studio()
    client = Mock(close=AsyncMock())
    studio.client = client
    studio.events.append({"event": "state", "data": {"track": "previous account"}})
    with pytest.raises(RuntimeError, match="catalogue cleanup failed"):
        await studio.close()
    client.close.assert_awaited_once()
    assert studio.client is None
    assert not studio.events
    assert (await studio.request("bootstrap", {}))["ok"] is False


def test_native_bridge_exposes_only_requests_and_login() -> None:
    bridge = Bridge(Mock(), Mock(), Mock(), Mock())
    assert {
        name
        for name in dir(bridge)
        if not name.startswith("_") and callable(getattr(bridge, name))
    } == {"request", "login"}
    assert bridge.request("search", {"query": 12})["ok"] is False
    assert bridge.request(None)["ok"] is False


@pytest.mark.parametrize("values", [False, 0, "", []])
def test_native_bridge_rejects_non_mapping_values(values: object) -> None:
    studio = Mock()
    bridge = Bridge(studio, Mock(), Mock(), Mock())

    assert bridge.request("search", values) == {
        "ok": False,
        "error": "Invalid application request",
    }
    studio.request.assert_not_called()


async def test_login_imports_only_its_own_spotify_cookie_and_never_returns_it() -> None:
    studio = Mock(authenticate=AsyncMock())
    window = Mock()
    window.get_current_url.return_value = "https://open.spotify.com/"
    window.get_cookies.return_value = [SimpleCookie("sp_dc=synthetic-cookie; unrelated=ignored")]
    notify = Mock()
    bridge = Bridge(studio, asyncio.get_running_loop(), Mock(), notify)
    bridge._login = window
    await asyncio.to_thread(bridge._capture_login)
    studio.authenticate.assert_awaited_once_with("sp_dc=synthetic-cookie")
    window.destroy.assert_called_once()
    notify.assert_called_once_with("signed_in")


async def test_login_never_imports_cookies_from_an_unrelated_page() -> None:
    studio = Mock(authenticate=AsyncMock())
    window = Mock()
    window.get_current_url.return_value = "https://open.spotify.com.example.test/"
    bridge = Bridge(studio, asyncio.get_running_loop(), Mock(), Mock())
    bridge._login = window
    await asyncio.to_thread(bridge._capture_login)
    window.get_cookies.assert_not_called()
    studio.authenticate.assert_not_awaited()


async def test_login_timeout_cancels_authentication_before_it_can_replace_the_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started, cancelled = asyncio.Event(), asyncio.Event()

    async def authenticate(cookie: str) -> None:
        started.set()
        try:
            await asyncio.Future[None]()
        finally:
            cancelled.set()

    monkeypatch.setattr("spotapi._studio.desktop._LOGIN_TIMEOUT", 0.05)
    studio = Mock(authenticate=authenticate)
    pending = asyncio.create_task(
        asyncio.to_thread(_authenticate, studio, asyncio.get_running_loop(), "sp_dc=synthetic")
    )
    await asyncio.wait_for(started.wait(), 1)
    assert not await pending
    await asyncio.wait_for(cancelled.wait(), 1)


async def test_repeated_loaded_callbacks_do_not_start_parallel_logins() -> None:
    started, finish = asyncio.Event(), asyncio.Event()

    async def authenticate(cookie: str) -> None:
        started.set()
        await finish.wait()

    studio = Mock(authenticate=AsyncMock(side_effect=authenticate))
    window = Mock()
    window.get_current_url.return_value = "https://open.spotify.com/"
    window.get_cookies.return_value = [SimpleCookie("sp_dc=synthetic-cookie")]
    bridge = Bridge(studio, asyncio.get_running_loop(), Mock(), Mock())
    bridge._login = window
    pending = asyncio.create_task(asyncio.to_thread(bridge._capture_login))
    await asyncio.wait_for(started.wait(), 1)
    try:
        await asyncio.to_thread(bridge._capture_login)
        studio.authenticate.assert_awaited_once()
    finally:
        finish.set()
        await pending


def test_bundled_page_contains_executable_app_and_fresh_csp_nonce() -> None:
    first, second = page(), page()
    assert "window.studio =" in first and "STUDIO_SCRIPT" not in first
    assert "--teal:" in first and "STUDIO_STYLE" not in first
    assert "{{nonce}}" not in first and first != second
    assert "connect-src 'none'" in first
    assert "https://accounts.spotify.com" not in first


def test_display_serializer_does_not_expose_challenge_secrets() -> None:
    data = serialize(
        AccountChallenge(
            "https://www.spotify.com/account/profile/challenge", "secret-session", "secret-nonce"
        )
    )
    assert set(data) == {"url"}
    with pytest.raises(TypeError):
        serialize(Studio())


@pytest.mark.parametrize("value", [float("nan"), float("inf"), {1: "invalid key"}])
def test_display_serializer_rejects_values_outside_json(value: object) -> None:
    with pytest.raises(TypeError):
        serialize(value)


def test_feature_identifiers_are_unique_and_changes_are_explicit() -> None:
    assert len({action.id for action in ACTIONS}) == len(ACTIONS)
    assert all(
        action.changes
        for action in ACTIONS
        if action.id
        in {
            "logout_everywhere",
            "edit_profile",
            "change_password",
            "edit_playlist",
            "delete_playlist",
        }
    )


async def test_studio_explains_a_missing_or_expired_login(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from spotapi import LoginExpired

    monkeypatch.setattr(Catalogue, "__aenter__", AsyncMock())
    monkeypatch.setattr(Catalogue, "close", AsyncMock())
    monkeypatch.setattr(Studio, "_execute", AsyncMock(side_effect=LoginExpired("private details")))
    studio = Studio()
    try:
        result = await studio.request("bootstrap", {})
        assert result == {"ok": False, "error": "Log in to Spotify again and update your session."}
    finally:
        await studio.close()


async def test_studio_overlaps_public_reads_without_blocking_each_other(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two unrelated searches must progress independently of the request mutex."""
    both_started = asyncio.Event()
    release = asyncio.Event()

    class CatalogueStub:
        calls = 0

        async def __aenter__(self) -> CatalogueStub:
            return self

        async def close(self) -> None:
            return None

        async def search(self, query: str, *, types: tuple[str, ...], limit: int) -> dict[str, str]:
            assert types and limit == 12
            self.calls += 1
            if self.calls == 2:
                both_started.set()
            await release.wait()
            return {"query": query}

    studio = Studio()
    monkeypatch.setattr(studio, "catalogue", CatalogueStub())
    first = asyncio.create_task(studio.request("search", {"query": "first"}))
    second = asyncio.create_task(studio.request("search", {"query": "second"}))
    try:
        await asyncio.wait_for(both_started.wait(), timeout=2)
    finally:
        release.set()

    results = await asyncio.gather(first, second)
    assert [value["data"]["query"] for value in results] == ["first", "second"]
    await studio.close()


async def test_studio_shutdown_drains_public_reads_before_closing_catalogue(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = asyncio.Event()
    release = asyncio.Event()

    class CatalogueStub:
        closed = False

        async def __aenter__(self) -> CatalogueStub:
            return self

        async def close(self) -> None:
            self.closed = True

        async def search(self, query: str, *, types: tuple[str, ...], limit: int) -> object:
            started.set()
            await release.wait()
            return {"query": query}

    stub = CatalogueStub()
    studio = Studio()
    monkeypatch.setattr(studio, "catalogue", stub)
    search = asyncio.create_task(studio.request("search", {"query": "in flight"}))
    await asyncio.wait_for(started.wait(), timeout=2)
    shutdown = asyncio.create_task(studio.close())
    await asyncio.sleep(0)
    assert not stub.closed
    assert not shutdown.done()
    release.set()
    assert (await search)["ok"] is True
    await shutdown
    assert stub.closed


def test_lyrics_identifies_installed_release(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("spotapi._studio.lyrics.package_version", lambda name: "2.7.3")
    assert _studio_user_agent() == (
        "SpotAPI Studio v2.7.3 (https://github.com/Aran404/SpotAPI)"
    )
