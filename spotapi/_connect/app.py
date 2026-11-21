"""A split-pane terminal remote for Spotify Connect.

The Textual widgets are presentation only. Player controls live devices,
Catalogue resolves metadata, and session.execute validates mutations. No
terminal button or completion may bypass those layers.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from typing import TYPE_CHECKING, Literal

from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.events import Key, MouseMove, Resize
from textual.message import Message
from textual.timer import Timer
from textual.widgets import Button, Input, OptionList, RichLog, Static
from textual.widgets.option_list import Option

from spotapi import Account, AsyncClient, Catalogue, Player
from spotapi.models import PlaybackTrack, PlayerState

from .auth import open_account
from .commands import parse_command
from .presentation import Identity, clock, device_row, progress_bar, queue_rows, search_row
from .queue import QueuePreview
from .session import execute
from .suggestions import completions

if TYPE_CHECKING:
    from spotapi.models.catalogue.track import Track


class HoverOptionList(OptionList):
    """Keep mouse hover and keyboard selection pointed at the same option."""

    def on_mouse_move(self, event: MouseMove) -> None:
        index = event.style.meta.get("option")
        if isinstance(index, int) and 0 <= index < self.option_count:
            self.highlighted = index


class ContextOptions(HoverOptionList):
    """A selectable list with mouse, keyboard, and a route back to the prompt."""

    class Alternate(Message):
        def __init__(self, key: Literal["q", "t"]) -> None:
            super().__init__()
            self.key = key

    class SwitchPanel(Message):
        def __init__(self, direction: Literal[-1, 1]) -> None:
            super().__init__()
            self.direction = direction

    class ReturnToPrompt(Message):
        pass

    def on_key(self, event: Key) -> None:
        key = event.key
        if key in ("q", "t"):
            self.post_message(self.Alternate(key))
        elif key in ("left", "right"):
            self.post_message(self.SwitchPanel(-1 if key == "left" else 1))
        elif key == "escape":
            self.post_message(self.ReturnToPrompt())
        else:
            return  # Let Textual handle ↑↓, Enter, Home/End, Page Up/Down.
        event.prevent_default()
        event.stop()


class CommandInput(Input):
    """Autocomplete is one interaction; submitting a command is another."""

    # Bound by ConnectApp.on_mount. Keeping this reference typed avoids using
    # Textual's App[Unknown] property inside a child widget under strict Pyright.
    suggestions_menu: HoverOptionList | None = None

    class Navigate(Message):
        def __init__(
            self,
            key: Literal["up", "down", "left", "right", "tab", "enter", "escape"],
        ) -> None:
            super().__init__()
            self.key = key

    def on_key(self, event: Key) -> None:
        key = event.key
        menu = self.suggestions_menu
        if menu is None:
            return
        if key in ("up", "down"):
            pass  # History when the popup is closed, suggestions otherwise.
        elif key in ("left", "right") and not self.value and not menu.display:
            pass  # An empty composer permits arrow-based view navigation.
        elif key in ("enter", "tab") and menu.display:
            # An already-complete command executes on Enter; partial suggestions
            # are only inserted, never sent to Spotify by accident.
            selected = menu.highlighted_option
            if (
                key == "enter"
                and selected is not None
                and selected.id is not None
                and self.value.strip().removeprefix("/").casefold() == selected.id.casefold()
            ):
                return
        elif key == "escape" and menu.display:
            pass
        else:
            # In particular Tab must still traverse widgets without a popup.
            return
        self.post_message(self.Navigate(key))
        event.prevent_default()
        event.stop()


class ConnectApp(App[None]):
    """One command composer, live playback, context, and an event timeline."""

    CSS_PATH = "style.tcss"
    TITLE = "SpotAPI Connect"
    BINDINGS = [
        Binding("ctrl+k", "suggest", "Commands", show=False),
        Binding("ctrl+l", "focus_command", "Focus input", show=False),
        Binding("alt+1", "panel('queue')", "Queue", show=False),
        Binding("alt+2", "panel('search')", "Results", show=False),
        Binding("alt+3", "panel('devices')", "Devices", show=False),
        Binding("alt+4", "panel('help')", "Help", show=False),
        Binding("ctrl+j", "focus_context", "Select result", show=False),
        Binding("alt+left", "cycle_panel(-1)", "Previous view", show=False),
        Binding("alt+right", "cycle_panel(1)", "Next view", show=False),
        Binding("ctrl+d", "show_devices", "Devices", show=False),
        Binding("ctrl+shift+l", "clear_logs", "Clear logs", show=False),
        Binding("f2", "toggle_logs", "Diagnostics", show=False),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(self, client: AsyncClient, *, profile: str = "default") -> None:
        super().__init__()
        self.client = client
        self.player = Player(client, name="SpotAPI Connect")
        self.catalogue = Catalogue(client)
        self._preview = QueuePreview(self.catalogue)
        self.profile = profile
        self.identity = Identity()
        self.hits: tuple[Track, ...] = ()
        self._queue_snapshot: tuple[PlaybackTrack, ...] = ()
        self._queue_items: tuple[PlaybackTrack, ...] = ()
        self._active_panel: Literal["queue", "devices", "search", "help"] = "queue"
        self._suggestions: tuple[str, ...] = ()
        self._accepted_completion: str | None = None
        self._context_options: tuple[tuple[str, str], ...] | None = None
        self._player_task: asyncio.Task[None] | None = None
        self._ui_ready = False
        self._refresh_timer: Timer | None = None
        self._command_busy = False
        self._shutting_down = False
        self._resources_closed = False
        self._retries = 0
        self._diagnostics_open = False
        self._history: list[str] = []
        self._history_index = -1
        self._recalling_history = False

        @self.player.listen("state_update")
        async def on_state(before: PlayerState | None, state: PlayerState) -> None:
            old_uri = before.track.uri if before and before.track else None
            current_uri = state.track.uri if state.track else None
            if current_uri is not None and current_uri != old_uri and state.track:
                self._activity(
                    f"Now playing  {state.track.artist} — {state.track.name}", "#9bf2a7"
                )
            if before is not None and before.is_paused != state.is_paused:
                self._activity("Paused" if state.is_paused else "Resumed", "#aecaaf")
            self._render_state()

        @self.player.listen("error")
        async def on_error(error: Exception) -> None:
            self._retries += 1
            if self._retries == 1:
                self._activity("Connection interrupted · trying again", "#e6c382")
            if self._retries == 1 or self._retries & (self._retries - 1) == 0:
                self._log(f"Retry {self._retries} · {type(error).__name__}")
            self._render_state()

        @self.player.listen("reconnect")
        async def on_reconnect() -> None:
            self._retries = 0
            self._activity("Spotify connection restored", "#9bf2a7")
            self._render_state()

    def compose(self) -> ComposeResult:
        """Keep logs visible beside playback, even as the composer stays pinned."""
        with Vertical(id="workspace"):
            with Horizontal(id="header"):
                yield Static("●  spotapi", id="brand")
                yield Static("/  CONNECT", id="mode")
                yield Static("○  connecting", id="connection")
            with Horizontal(id="account-strip"):
                yield Static("account / connecting", id="account")
                yield Static("device / waiting for Spotify", id="device")
            with Horizontal(id="split"):
                with Vertical(id="player-pane"):
                    yield Static("01   /   NOW PLAYING", id="eyebrow")
                    yield Static("Waiting for Spotify", id="track")
                    yield Static("Start a song on any Spotify player", id="artist")
                    yield Static("", id="progress")
                    yield Static("", id="details")
                    with Horizontal(id="transport"):
                        yield Button("◀  prev", id="previous", classes="transport-link")
                        yield Button("Ⅱ  pause", id="toggle", classes="transport-link primary")
                        yield Button("next  ▶", id="next", classes="transport-link")
                    with Horizontal(id="context-tabs"):
                        yield Button("queue", id="tab-queue", classes="tab-button active")
                        yield Button("results", id="tab-search", classes="tab-button")
                        yield Button("devices", id="tab-devices", classes="tab-button")
                        yield Button("help", id="tab-help", classes="tab-button")
                    yield Static("UP NEXT   /   SPOTIFY SNAPSHOT", id="context-label")
                    yield Static("No upcoming tracks reported by Spotify.", id="context-content")
                    yield ContextOptions(id="context-options", compact=True, markup=False)
                with Vertical(id="activity-pane"):
                    with Horizontal(id="activity-header"):
                        yield Static("02   /   ACTIVITY", id="channel-label")
                        yield Button("logs  F2", id="logs-toggle", classes="subtle-link")
                    yield Static(
                        "Commands and Spotify events  ·  scroll to inspect",
                        id="activity-subtitle",
                    )
                    yield RichLog(id="activity", max_lines=300, auto_scroll=True, wrap=True)
                    yield RichLog(id="diagnostics", max_lines=200, auto_scroll=True, wrap=True)
            yield Static(
                " ←→ views   ↑↓ browse   Enter play / target   Q queue   T transfer   Esc prompt",
                id="shortcut-hint",
            )
            yield HoverOptionList(id="suggestions", compact=True, markup=False)
            with Horizontal(id="composer"):
                yield Static("spotapi@spotify ~ $", id="prompt")
                yield CommandInput(
                    placeholder="Type a command  ·  search Radiohead  ·  /help",
                    id="command",
                    select_on_focus=False,
                )

    async def on_mount(self) -> None:
        menu = self.query_one("#suggestions", HoverOptionList)
        menu.display = False
        self.query_one("#command", CommandInput).suggestions_menu = menu
        self.query_one("#context-options", ContextOptions).display = False
        self.query_one("#diagnostics", RichLog).display = False
        self._ui_ready = True
        try:
            await self.catalogue.__aenter__()
        except Exception as error:
            self._log(f"Catalogue initialization · {type(error).__name__}")
            self._activity(
                "Catalogue unavailable · searches will not work this session", "#e8a49c"
            )
            # Search can fail independently of the live Connect controller.
            # Still start the playback supervisor, devices and command input.
        self._activity(f"Session started · profile {self.profile}")
        self._activity("Spotify Connect is listening for playback updates")
        self._activity("Type / for commands · click the controls to interact")
        self._player_task = asyncio.create_task(self.player.start(), name="spotapi-connect")
        self._player_task.add_done_callback(self._on_supervisor_done)
        self._load_identity()
        self._refresh_timer = self.set_interval(0.5, self._render_state)
        self._render_state()
        self.query_one("#command", CommandInput).focus()

    @work(group="account", exclusive=True, exit_on_error=False)
    async def _load_identity(self) -> None:
        """Prefer Spotify's recognizable public name over its opaque account ID."""
        try:
            account = await asyncio.wait_for(Account(self.client).get_profile(), timeout=8)
        except Exception as error:
            self._log(f"Account lookup · {type(error).__name__}")
            self._render_state()
            return
        self.identity = Identity(username=account.username)
        self._render_state()
        try:
            public = await asyncio.wait_for(
                self.catalogue.get_profile(account.username, limit=1), timeout=8
            )
        except Exception as error:
            self._log(f"Public display name unavailable · {type(error).__name__}")
            return
        if public.name.strip():
            self.identity = Identity(username=account.username, display_name=public.name.strip())
            self._render_state()

    def _on_supervisor_done(self, task: asyncio.Task[None]) -> None:
        if self._shutting_down or task.cancelled():
            return
        error = task.exception()
        self._log(
            f"Supervisor stopped · {type(error).__name__}" if error else "Supervisor stopped"
        )
        self._activity("Connect stopped unexpectedly. Restart to reconnect.", "#e8a49c")
        self._render_state()

    def _entry(self, widget_id: str, message: str, color: str) -> None:
        if not self._ui_ready:
            return
        entry = Text(datetime.now().strftime("%H:%M:%S  "), style="#728b79")
        entry.append(message.replace("\n", " ")[:350], style=color)
        self.query_one(widget_id, RichLog).write(entry)

    def _activity(self, message: str, color: str = "#c2d5c3") -> None:
        self._entry("#activity", message, color)

    def _log(self, message: str) -> None:
        # Only exception *types*, never raw URLs, tokens, headers or cookies.
        self._entry("#diagnostics", message, "#a8baa9")

    def _render_state(self) -> None:
        if not self._ui_ready:
            return
        state = self.player.state
        target = self.player.target_device_id
        active = state.active_device_id if state else None
        selected = target is not None and target != active
        device = next(
            (value for value in self.player.devices if value.id == (target or active)), None
        )
        name = device.name if device else "No active player"
        status = (
            "● live"
            if self.player.is_ready
            else "◌ reconnecting" if self._retries else "○ connecting"
        )
        if self._player_task is not None and self._player_task.done():
            status = "○ offline"
        try:
            connection = self.query_one("#connection", Static)
        except NoMatches:
            # Textual may detach the screen before dispatching Shutdown,
            # notably when run_test exits on Windows.
            self._ui_ready = False
            if self._refresh_timer is not None:
                self._refresh_timer.stop()
                self._refresh_timer = None
            return
        connection.update(status)
        self.query_one("#account", Static).update(
            f"account  /  {self.identity.label}    ·    profile {self.profile}"
        )
        self.query_one("#device", Static).update(
            f"device  /  {name}" + ("  ·  target only" if selected else "")
        )
        self.query_one("#prompt", Static).update(self.identity.prompt)

        actionable = (
            self.player.is_ready and state is not None and state.track is not None and not selected
        )
        for button_id in ("previous", "toggle", "next"):
            self.query_one(f"#{button_id}", Button).disabled = not actionable
        self.query_one("#toggle", Button).label = (
            "▶  resume" if state is None or state.is_paused else "Ⅱ  pause"
        )
        if not actionable:
            self.query_one("#track", Static).update(
                "Control a selected device"
                if selected
                else "Waiting for Spotify" if not self.player.is_ready else "Nothing playing"
            )
            self.query_one("#artist", Static).update(
                "Use transfer N to move playback"
                if selected
                else "Open Spotify on an existing device and press play"
            )
            self.query_one("#progress", Static).update(" ")
            self.query_one("#details", Static).update(
                f"{len(self.player.devices)} device(s) discovered · type devices to browse"
            )
        else:
            assert state is not None and state.track is not None
            self.query_one("#track", Static).update(state.track.name or "Unknown track")
            self.query_one("#artist", Static).update(
                "  ·  ".join(part for part in (state.track.artist, state.track.album) if part)
            )
            meter = self.query_one("#progress", Static)
            width = max(8, min(23, meter.size.width - 18))
            meter.update(
                Text.assemble(
                    (clock(state.position_ms), "bold #a8f3b5"),
                    (f"  {progress_bar(state.progress, width=width)}  ", "#6fce91"),
                    (clock(state.duration_ms), "#7f9292"),
                )
            )
            vol = device.volume_percent if device else None
            self.query_one("#details", Static).update(
                f"{'Paused' if state.is_paused else 'Playing'}"
                f"  ·  Volume {vol if vol is not None else '—'}"
                f"  ·  Shuffle {'on' if state.shuffle else 'off'}  ·  Repeat {state.repeat_mode}"
            )
        queue = state.next_tracks[:8] if state and self.player.is_ready and not selected else ()
        if queue != self._queue_snapshot:
            self._queue_snapshot = queue
            self._queue_items = queue
            if queue:
                self._enrich_queue(queue)
        self._render_context()

    @work(group="queue", exclusive=True, exit_on_error=False)
    async def _enrich_queue(self, queue: tuple[PlaybackTrack, ...]) -> None:
        items = await self._preview.enrich(queue)
        if queue == self._queue_snapshot:
            self._queue_items = items
            self._render_context()

    def _render_context(self) -> None:
        """Keep the live queue read-only; results and devices are selectable."""
        if not self._ui_ready:
            return
        label = self.query_one("#context-label", Static)
        content = self.query_one("#context-content", Static)
        options = self.query_one("#context-options", ContextOptions)
        for name in ("queue", "devices", "search", "help"):
            self.query_one(f"#tab-{name}", Button).set_class(self._active_panel == name, "active")

        rows: tuple[tuple[str, str], ...] = ()
        match self._active_panel:
            case "devices":
                label.update(
                    f"DEVICES / {len(self.player.devices)} FOUND  ·  ENTER TARGET  ·  T TRANSFER"
                )
                state = self.player.state
                active = state.active_device_id if state is not None else None
                target = self.player.target_device_id
                rows = tuple(
                    (
                        f"device:{device.id}",
                        device_row(index, device, active=active, target=target),
                    )
                    for index, device in enumerate(self.player.devices, 1)
                )
                content.update("No devices found. Open Spotify on an existing player.")
            case "search":
                label.update(f"RESULTS   /   {len(self.hits)} TRACKS   ·   ENTER PLAY · Q QUEUE")
                rows = tuple(
                    (f"track:{index}", search_row(index, hit))
                    for index, hit in enumerate(self.hits, 1)
                )
                content.update("Search for an artist or track: search Radiohead")
            case "help":
                label.update("HELP   /   TYPE ANY COMMAND AT THE PROMPT")
                content.update(
                    "SEARCH   search Daft Punk · play 1 · queue 1\n"
                    "PLAYER   pause · resume · toggle · next · previous\n"
                    "MOVE     devices · use 1 · transfer 1\n"
                    "ADJUST   seek 1:30 · volume 50 · shuffle on\n"
                    "SESSION  refresh · clear / cls · exit / exit()\n"
                    "NAV      ←→ views · Ctrl+J browse · Esc prompt\n"
                    "         ↑↓ select · Enter play · Q queue · T transfer"
                )
            case "queue":
                label.update("UP NEXT   /   OBSERVED SPOTIFY QUEUE")
                content.update(queue_rows(self._queue_items, limit=8))

        if rows != self._context_options:
            previously_selected = options.highlighted_option
            previous_id = previously_selected.id if previously_selected else None
            options.clear_options()
            options.add_options(
                Option(self._row_text(text), id=identifier) for identifier, text in rows
            )
            self._context_options = rows
            if rows:
                ids = [identifier for identifier, _ in rows]
                options.highlighted = ids.index(previous_id) if previous_id in ids else 0
        options.display = bool(rows)
        content.display = not rows

    @staticmethod
    def _row_text(value: str) -> Text:
        """Draw subtle row numbers and accessible one-line summaries."""
        row = Text()
        row.append(value[:2], style="bold #84e8a1")
        row.append(value[2:], style="#d5e8d7")
        return row

    @on(Input.Changed, "#command")
    def command_changed(self, event: Input.Changed) -> None:
        menu = self.query_one("#suggestions", HoverOptionList)
        # Input.Changed is delivered asynchronously. Completing an option
        # updates Input.value, which can otherwise reopen the popup *after*
        # _complete() hides it. Preserve the accepted value until the user
        # actually edits the composer again.
        if event.value == self._accepted_completion:
            menu.display = False
            return
        self._accepted_completion = None
        if self._recalling_history:
            self._recalling_history = False
            menu.display = False
            return
        source = event.value.strip()
        if not source or len(source) > 100:
            menu.display = False
            self._suggestions = ()
            return
        candidates = completions(source)
        self._suggestions = tuple(item.example for item in candidates)
        menu.clear_options()
        menu.add_options(
            Option(
                Text.assemble(
                    (f"{item.example:<22}", "bold #9bf2a7"), (item.description, "#b5c5d0")
                ),
                id=item.example,
            )
            for item in candidates
        )
        menu.display = bool(candidates)
        if candidates:
            menu.highlighted = None

    @on(CommandInput.Navigate)
    def navigate_suggestions(self, event: CommandInput.Navigate) -> None:
        menu = self.query_one("#suggestions", HoverOptionList)
        if event.key in ("left", "right"):
            self.action_cycle_panel(-1 if event.key == "left" else 1)
            return
        if not menu.display and event.key in ("up", "down"):
            self._recall_history(event.key)
            return
        count = len(self._suggestions)
        if event.key == "escape":
            menu.display = False
            return
        if not count:
            return
        index = menu.highlighted
        if event.key == "down":
            menu.highlighted = 0 if index is None else (index + 1) % count
        elif event.key == "up":
            menu.highlighted = count - 1 if index is None else (index - 1) % count
        elif event.key in ("tab", "enter"):
            self._complete(self._suggestions[index if index is not None else 0])

    def _recall_history(self, direction: Literal["up", "down"]) -> None:
        """Bash-style command recall, separate from popup selection."""
        if not self._history:
            return
        if direction == "up":
            self._history_index = min(self._history_index + 1, len(self._history) - 1)
        else:
            self._history_index = max(-1, self._history_index - 1)
        command = self._history[-self._history_index - 1] if self._history_index >= 0 else ""
        field = self.query_one("#command", CommandInput)
        self._recalling_history = field.value != command
        field.value = command

    @on(OptionList.OptionSelected, "#suggestions")
    def suggestion_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self._complete(event.option_id)

    def _complete(self, value: str) -> None:
        menu = self.query_one("#suggestions", HoverOptionList)
        self._accepted_completion = value
        menu.display = False
        field = self.query_one("#command", CommandInput)
        field.value = value
        # Input.Changed can reopen suggestions; close *after* setting the value.
        menu.display = False
        field.cursor_position = len(field.value)
        field.focus()

    @on(Input.Submitted, "#command")
    def command_submitted(self, event: Input.Submitted) -> None:
        """Only explicit submission executes; completion never mutates Spotify."""
        value = event.value.strip()
        menu = self.query_one("#suggestions", HoverOptionList)
        if menu.display and self._suggestions:
            selected = menu.highlighted
            candidate = self._suggestions[selected if selected is not None else 0]
            if value.removeprefix("/").casefold() != candidate.casefold():
                self._complete(candidate)
                return
        if not value:
            self.action_suggest()
            return
        menu = self.query_one("#suggestions", HoverOptionList)
        menu.display = False
        self._issue(value)
        self.query_one("#command", CommandInput).value = ""

    @on(OptionList.OptionSelected, "#context-options")
    def context_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_id:
            self._activate_context(event.option_id)

    @on(ContextOptions.Alternate)
    def context_alternate(self, event: ContextOptions.Alternate) -> None:
        selected = self.query_one("#context-options", ContextOptions).highlighted_option
        if selected is None or selected.id is None:
            return
        if (event.key == "q" and selected.id.startswith("track:")) or (
            event.key == "t" and selected.id.startswith("device:")
        ):
            self._activate_context(selected.id, alternate=True)

    def _activate_context(self, identifier: str, *, alternate: bool = False) -> None:
        """Resolve current indexes by stable device ID before dispatching."""
        kind, _, value = identifier.partition(":")
        if kind == "track" and value.isascii() and value.isdecimal():
            if 1 <= int(value) <= len(self.hits):
                self._issue(f"{'queue' if alternate else 'play'} {value}", keep_list_focus=True)
        elif kind == "device":
            for index, device in enumerate(self.player.devices, 1):
                if device.id == value:
                    self._issue(
                        f"{'transfer' if alternate else 'use'} {index}",
                        keep_list_focus=True,
                    )
                    return
            self._activity("That device disappeared; refresh the device list", "#e6c382")

    def _issue(self, source: str, *, keep_list_focus: bool = False) -> None:
        """Every invocation has visible feedback, including rejected overlap."""
        if self._shutting_down:
            return
        try:
            command = parse_command(source)
        except ValueError:
            command = None
        # Local lifecycle commands must work even during a slow network action.
        if command is not None:
            if command.action == "clear":
                self.action_clear_logs()
                return
            if command.action == "quit":
                self.exit()
                return
        if self._command_busy:
            self._activity("Previous command still running; wait for its result", "#e6c382")
            return
        if not self._history or self._history[-1] != source:
            self._history.append(source)
            del self._history[:-40]
        self._history_index = -1
        self._command_busy = True
        self._run_command(source, keep_list_focus=keep_list_focus)

    @work(group="commands", exclusive=True, exit_on_error=False)
    async def _run_command(self, source: str, *, keep_list_focus: bool) -> None:
        focus_context = keep_list_focus
        try:
            command = parse_command(source)
            self._activity(
                f"❯ {command.action}" + (f" {command.argument}" if command.argument else "")
            )
            result = await execute(
                command, player=self.player, catalogue=self.catalogue, hits=self.hits
            )
            if result.search_hits is not None:
                self.hits = result.search_hits
                self._active_panel = "search"
                focus_context = bool(result.search_hits)
            elif command.action == "devices":
                self._active_panel = "devices"
                focus_context = bool(self.player.devices)
            elif command.action == "help":
                self._active_panel = "help"
            elif command.action == "refresh":
                self._active_panel = "queue"
            if command.action == "quit":
                self.exit()
            else:
                self._activity(result.message.splitlines()[0], "#9bf2a7")
            self._render_state()
        except TimeoutError:
            self._activity("No confirmation received; check Spotify before retrying", "#e6c382")
            self._log("Command acknowledgement timed out · no automatic retries")
        except (ValueError, RuntimeError) as error:
            self._activity(str(error), "#e8a49c")
        except Exception as error:
            self._activity("Command failed · press F2 for diagnostic type", "#e8a49c")
            self._log(f"Command failed · {type(error).__name__}")
        finally:
            self._command_busy = False
            if not self._shutting_down:
                options = self.query_one("#context-options", ContextOptions)
                if focus_context and options.display:
                    options.focus()
                else:
                    self.action_focus_command()

    @on(Button.Pressed)
    def on_button_pressed(self, event: Button.Pressed) -> None:
        match event.button.id:
            case "tab-queue":
                self.action_panel("queue")
            case "tab-search":
                self.action_panel("search")
            case "tab-devices":
                self.action_panel("devices")
            case "tab-help":
                self.action_panel("help")
            case "previous":
                self._issue("previous")
            case "toggle":
                self._issue("toggle")
            case "next":
                self._issue("next")
            case "devices":
                self._issue("devices")
            case "logs-toggle":
                self.action_toggle_logs()
            case _:
                return

    def action_panel(self, name: Literal["queue", "search", "devices", "help"]) -> None:
        """Switch views without hiding the composer or sacrificing mouse support."""
        self._active_panel = name
        self._render_context()
        options = self.query_one("#context-options", ContextOptions)
        if options.display:
            options.focus()
        else:
            self.action_focus_command()

    def action_cycle_panel(self, direction: int) -> None:
        """Arrow navigation is cyclic; arrow keys in typed input still move its caret."""
        panels: tuple[Literal["queue", "search", "devices", "help"], ...] = (
            "queue",
            "search",
            "devices",
            "help",
        )
        index = panels.index(self._active_panel)
        self.action_panel(panels[(index + direction) % len(panels)])

    @on(ContextOptions.SwitchPanel)
    def context_switch_panel(self, event: ContextOptions.SwitchPanel) -> None:
        self.action_cycle_panel(event.direction)

    @on(ContextOptions.ReturnToPrompt)
    def context_return_to_prompt(self, event: ContextOptions.ReturnToPrompt) -> None:
        self.action_focus_command()

    def action_show_devices(self) -> None:
        self.action_panel("devices")

    def action_focus_context(self) -> None:
        """Focus the current list, or the available search/device list."""
        if self._active_panel not in ("search", "devices"):
            if self.hits:
                self._active_panel = "search"
            elif self.player.devices:
                self._active_panel = "devices"
        self._render_context()
        options = self.query_one("#context-options", ContextOptions)
        if options.display:
            options.focus()
        else:
            self._activity("No results or devices to select yet; try search Radiohead")
            self.action_focus_command()

    def action_clear_logs(self) -> None:
        """Clear the activity and diagnostic streams, not Spotify's queue."""
        self.query_one("#activity", RichLog).clear()
        self.query_one("#diagnostics", RichLog).clear()

    def action_focus_command(self) -> None:
        self.query_one("#command", CommandInput).focus()

    def action_suggest(self) -> None:
        field = self.query_one("#command", CommandInput)
        field.value = "/"
        field.focus()

    def action_toggle_logs(self) -> None:
        self._diagnostics_open = not self._diagnostics_open
        self.query_one("#activity", RichLog).display = not self._diagnostics_open
        self.query_one("#diagnostics", RichLog).display = self._diagnostics_open
        self.query_one("#channel-label", Static).update(
            "DIAGNOSTICS" if self._diagnostics_open else "ACTIVITY"
        )
        self.query_one("#activity-subtitle", Static).update(
            "Diagnostic event types · no credentials or tokens"
            if self._diagnostics_open
            else "Commands and Spotify events  ·  scroll to inspect"
        )
        self.query_one("#logs-toggle", Button).label = (
            "activity  F2" if self._diagnostics_open else "logs  F2"
        )

    def on_resize(self, event: Resize) -> None:
        self.set_class(event.size.width < 90, "narrow")
        self.set_class(event.size.height < 30, "short")
        self.set_class(event.size.height < 23, "tiny")

    def on_shutdown(self) -> None:
        """Stop UI callbacks before Textual dismantles the widget tree."""
        self._ui_ready = False
        self._shutting_down = True
        if self._refresh_timer is not None:
            self._refresh_timer.stop()
            self._refresh_timer = None

    async def on_unmount(self) -> None:
        await self.close_connections()

    async def close_connections(self) -> None:
        """Close player before HTTP catalogue; idempotent across shutdown paths."""
        if self._resources_closed:
            return
        self._resources_closed = True
        self.on_shutdown()
        try:
            await self.player.close()
        finally:
            if self._player_task is not None:
                if not self._player_task.done():
                    self._player_task.cancel()
                await asyncio.gather(self._player_task, return_exceptions=True)
            await self.catalogue.close()


async def run_connect(profile: str, *, force: bool = False) -> None:
    """Create one authenticated client, and release it after the TUI exits."""
    client = await open_account(profile, force=force)
    async with client:
        app = ConnectApp(client, profile=profile)
        try:
            await app.run_async()
        finally:
            await app.close_connections()
