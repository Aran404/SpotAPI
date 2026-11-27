"""Deterministic tests for Connect's interaction and queue presentation rules."""

from __future__ import annotations

from collections.abc import Callable
from types import SimpleNamespace
from typing import TYPE_CHECKING, TypeVar, cast
from unittest.mock import AsyncMock

import pytest

from spotapi._connect.queue import QueuePreview
from spotapi._connect.suggestions import completions
from spotapi.models import PlaybackTrack

if TYPE_CHECKING:
    from spotapi.catalogue import Catalogue
    from spotapi.client import AsyncClient


def test_command_suggestions_include_descriptions() -> None:
    matches = completions("/se")
    assert matches
    assert matches[0].example == "seek 1:30"
    assert all(match.description for match in matches)
    assert completions("next")[0].example == "next"
    assert completions("/shuffle")
    assert completions("nonsense") == ()


def test_command_suggestions_do_not_expose_arbitrary_shell_commands() -> None:
    assert not completions("sudo")
    assert not completions("rm -rf")
    assert len(completions("/")) <= 6


@pytest.mark.asyncio
async def test_queue_preview_preserves_order_occurrences_and_metadata() -> None:
    artist = SimpleNamespace(profile=SimpleNamespace(name="An Artist"))
    track = SimpleNamespace(
        name="Track title",
        first_artist=SimpleNamespace(items=(artist,)),
        other_artists=None,
    )
    catalogue = SimpleNamespace(get_track=AsyncMock(return_value=track))
    preview = QueuePreview(cast("Catalogue", catalogue))
    tracks = (
        PlaybackTrack(uri="spotify:track:abc", uid="one", provider="queue"),
        PlaybackTrack(uri="spotify:track:abc", uid="two", provider="context"),
    )
    resolved = await preview.enrich(tracks)
    assert [item.uid for item in resolved] == ["one", "two"]
    assert [item.provider for item in resolved] == ["queue", "context"]
    assert all(item.name == "Track title" and item.artist == "An Artist" for item in resolved)
    catalogue.get_track.assert_awaited_once_with("spotify:track:abc")
    await preview.enrich(tracks)
    catalogue.get_track.assert_awaited_once()


@pytest.mark.asyncio
async def test_queue_preview_never_adds_inferred_tracks() -> None:
    catalogue = SimpleNamespace(get_track=AsyncMock())
    preview = QueuePreview(cast("Catalogue", catalogue))
    assert await preview.enrich(()) == ()
    item = PlaybackTrack(uri="spotify:episode:real", name="Episode", uid="one")
    assert await preview.enrich((item,)) == (item,)
    catalogue.get_track.assert_not_awaited()


@pytest.mark.asyncio
async def test_queue_metadata_lookup_failure_does_not_hide_entry() -> None:
    catalogue = SimpleNamespace(get_track=AsyncMock(side_effect=TimeoutError()))
    preview = QueuePreview(cast("Catalogue", catalogue))
    item = PlaybackTrack(uri="spotify:track:unresolved", uid="live")
    assert await preview.enrich((item,)) == (item,)


@pytest.mark.asyncio
async def test_connect_command_completion_mouse_and_keyboard(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("textual")
    from textual.widgets import OptionList

    from spotapi._connect import app as ui

    Callback = TypeVar("Callback", bound=Callable[..., object])

    class FakeCatalogue:
        def __init__(self, client: object) -> None:
            self.client = client

        async def __aenter__(self) -> FakeCatalogue:
            return self

        async def close(self) -> None:
            return None

    class FakePlayer:
        state = None
        devices: tuple[()] = ()
        target_device_id = None
        is_ready = False

        def __init__(self, client: object, *, name: str) -> None:
            pass

        def listen(self, name: str) -> Callable[[Callback], Callback]:
            def register(callback: Callback) -> Callback:
                return callback

            return register

        async def start(self) -> None:
            import asyncio

            await asyncio.Event().wait()

        async def close(self) -> None:
            pass

    monkeypatch.setattr(ui, "Catalogue", FakeCatalogue)
    monkeypatch.setattr(ui, "Player", FakePlayer)

    def skip_profile_load(self: ui.ConnectApp) -> None:
        return None

    monkeypatch.setattr(ui.ConnectApp, "_load_identity", skip_profile_load)
    application = ui.ConnectApp(cast("AsyncClient", SimpleNamespace()))
    async with application.run_test(size=(112, 40)) as pilot:
        command = application.query_one("#command", ui.CommandInput)
        command.value = "/se"
        await pilot.pause()
        suggestions = application.query_one("#suggestions", OptionList)
        assert command.suggestions_menu is application.query_one(
            "#suggestions", ui.HoverOptionList
        )
        assert suggestions.display
        await pilot.press("down", "enter")
        await pilot.pause()
        assert command.value == "seek 1:30"
        assert not suggestions.display
        # A genuine subsequent edit must allow suggestions to reopen.
        command.value = "/se"
        await pilot.pause()
        assert suggestions.display


def test_shell_prompt_prefers_authenticated_spotify_username() -> None:
    from spotapi._connect.presentation import Identity

    assert Identity().prompt == "spotapi@spotify ~ $"
    assert Identity(username="real_user", display_name="Cool Display").prompt == (
        "spotapi@real_user ~ $"
    )
    assert Identity(display_name="Cool Display").prompt == "spotapi@Cool_Display ~ $"
    assert Identity(username="first name").prompt == "spotapi@first_name ~ $"


def test_connect_css_ids_exist_in_the_tui() -> None:
    """A stale CSS selector caused the original UI to lose almost all styling."""
    import ast
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "spotapi" / "_connect"
    source = (root / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    widgets = {
        keyword.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "id"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }
    css = re.sub(r"/\*.*?\*/", "", (root / "style.tcss").read_text(), flags=re.S)
    selectors = " ".join(re.findall(r"([^{}]+)\{", css))
    styled = set(re.findall(r"#([a-z][a-z0-9-]+)", selectors))
    assert styled <= widgets, f"Unknown widget ID(s) in stylesheet: {styled - widgets}"
    assert {"header", "player-pane", "activity-pane", "composer", "prompt"} <= styled


def test_search_results_have_useful_optional_metadata() -> None:
    from spotapi._connect.presentation import search_row
    from spotapi.models.catalogue.track import ArtistItem, ArtistProfile, Artists, Duration, Track

    hit = Track(
        id="t",
        name="Let Down",
        uri="spotify:track:t",
        artists=Artists(
            items=[ArtistItem(uri="spotify:artist:a", profile=ArtistProfile("Radiohead"))]
        ),
        duration=Duration(total_milliseconds=299_000),
    )
    assert search_row(2, hit) == "02  Let Down   ·   Radiohead  ·  4:59"
    assert search_row(1, Track(id="x", name="Unknown", uri="spotify:track:x")) == "01  Unknown"


def test_display_truncation_uses_terminal_cells() -> None:
    from rich.cells import cell_len

    from spotapi._connect.presentation import _short

    assert _short("abc", 3) == "abc"
    assert _short("日本語", 5) == "日本…"
    assert cell_len(_short("日本語", 4)) <= 4


def test_device_rows_distinguish_playing_target_and_idle() -> None:
    from spotapi._connect.presentation import device_row
    from spotapi.models.playback import Device

    first = Device(id="a", name="Browser", type="Computer")
    second = Device(id="b", name="Smart Speaker", type="Speaker")
    assert "● playing" in device_row(1, first, active="a", target="b")
    assert "◎ target" in device_row(2, second, active="a", target="b")
    assert "○ ready" in device_row(2, second, active="a", target=None)


@pytest.mark.asyncio
async def test_results_and_devices_are_keyboard_navigable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Runs with the optional connect extra, no live Spotify calls."""
    pytest.importorskip("textual")
    import asyncio

    from textual.widgets import Input

    from spotapi._connect import app as ui
    from spotapi.models.catalogue.track import Track
    from spotapi.models.playback import Device

    class FakeCatalogue:
        def __init__(self, client: object) -> None:
            pass

        async def __aenter__(self) -> FakeCatalogue:
            return self

        async def close(self) -> None:
            pass

    class FakePlayer:
        state = None
        target_device_id = None
        is_ready = False
        devices = (Device(id="a", name="Desktop"), Device(id="b", name="Browser"))

        def __init__(self, client: object, *, name: str) -> None:
            pass

        def listen(self, name: str) -> Callable[[Callable[..., object]], Callable[..., object]]:
            def register(callback: Callable[..., object]) -> Callable[..., object]:
                return callback

            return register

        async def start(self) -> None:
            await asyncio.Event().wait()

        async def close(self) -> None:
            pass

    monkeypatch.setattr(ui, "Catalogue", FakeCatalogue)
    monkeypatch.setattr(ui, "Player", FakePlayer)

    def skip_profile_load(self: ui.ConnectApp) -> None:
        return None

    monkeypatch.setattr(ui.ConnectApp, "_load_identity", skip_profile_load)
    application = ui.ConnectApp(cast("AsyncClient", SimpleNamespace()))
    commands: list[str] = []

    def capture_issue(source: str, *, keep_list_focus: bool = False) -> None:
        commands.append(source)

    monkeypatch.setattr(application, "_issue", capture_issue)
    async with application.run_test(size=(120, 39)) as pilot:
        application.hits = (
            Track(id="one", uri="spotify:track:one", name="First"),
            Track(id="two", uri="spotify:track:two", name="Second"),
        )
        application.action_panel("search")
        await pilot.press("down", "enter")
        await pilot.pause()
        assert commands[-1] == "play 2"

        await pilot.press("left")
        await pilot.pause()
        assert application._active_panel == "queue"
        await pilot.press("right", "right")
        await pilot.pause()
        assert application._active_panel == "devices"
        await pilot.press("down", "t")
        await pilot.pause()
        assert commands[-1] == "transfer 2"

        await pilot.press("escape")
        await pilot.pause()
        assert application.focused is application.query_one("#command", Input)

        for width, height in ((80, 32), (60, 24), (40, 20), (120, 39)):
            await pilot.resize_terminal(width, height)
            await pilot.pause()
            assert application.has_class("narrow") == (width < 90)
            assert application.has_class("short") == (height < 30)
            assert application.has_class("tiny") == (height < 23)
            assert application.query_one("#command", Input).region.bottom <= height
            assert application.focused is application.query_one("#command", Input)
