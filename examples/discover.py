"""♫ SpotAPI Discover: all of Spotify in your terminal. No login, no API key, no OAuth.

    pip install spotapi textual textual-image httpx
    python discover.py                    # surprise me
    python discover.py "Kendrick Lamar"

Ten catalogue tabs support paged search and direct Spotify links. Press Enter on anything
to dive in: a focused view with relevant artwork, facts and contributor credits,
ready to compare with open.spotify.com or copy out as JSON.

Paste a playlist link to see its tracks, BPM and harmonic keys when available.
"""

from __future__ import annotations

import asyncio
import json
import random
import sys
import webbrowser
from collections.abc import (
    AsyncGenerator,
    Awaitable,
    Callable,
    Sequence,
)
from contextlib import aclosing
from dataclasses import asdict, dataclass, field, is_dataclass
from functools import partial
from io import BytesIO
from time import perf_counter
from typing import Any, Protocol, TypeVar

import httpx
from PIL import Image as pil
from rich.console import Group
from rich.markup import escape
from rich.pretty import Pretty
from rich.rule import Rule
from rich.text import Text
from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.theme import Theme
from textual.widget import Widget
from textual.widgets import (
    Button,
    DataTable,
    Footer,
    Header,
    Input,
    Static,
    TabbedContent,
    TabPane,
)
from textual_image.widget import Image

from spotapi import Catalogue, Public

try:
    from .details import at, items, node, present
except ImportError:
    from details import at, items, node, present
from spotapi.models import (
    ArtistDetails,
    ArtistRelease,
    PlaylistDetails,
    PlaylistEntry,
    PlaylistTrack,
    TrackCredits,
    TrackDetails,
)

T = TypeVar("T")


class Hit(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def uri(self) -> str: ...


GREEN = "#1DB954"
PREFETCH = 8  # fetch the next page when the cursor is this many rows from the end
MAX_RESULTS = 1000
DEBOUNCE = 0.15  # seconds the cursor must rest on a row before we look it up
SUGGESTIONS = (
    "Drake",
    "Juice WRLD",
    "Kendrick Lamar",
    "Taylor Swift",
    "The Daily",
)
SPOTIFY = Theme(
    name="spotify", primary=GREEN, secondary="#1ED760", accent=GREEN,
    background="#121212", surface="#181818", panel="#282828", dark=True,
)  # fmt: skip


async def first(stream: AsyncGenerator[T, None]) -> T | None:
    """Take the first page from a stream (None if empty) and always close it."""
    async with aclosing(stream):
        return await anext(stream, None)


@dataclass(slots=True)
class PlaylistView:
    playlist: PlaylistDetails
    items: Sequence[PlaylistEntry]


@dataclass(slots=True)
class TrackView:
    track: TrackDetails
    credits: TrackCredits


async def lookup_track(uri: str, *, api: Catalogue) -> TrackView:
    track, credits = await asyncio.gather(api.get_track(uri), api.get_track_credits(uri))

    return TrackView(track, credits)


@dataclass(slots=True)
class ArtistView:
    artist: ArtistDetails
    releases: Sequence[ArtistRelease]


async def lookup_artist(uri: str, *, api: Catalogue) -> ArtistView:
    artist, releases = await asyncio.gather(
        api.get_artist(uri), first(api.get_artist_releases(uri, limit=20))
    )

    return ArtistView(artist, releases or ())


async def lookup_playlist(uri: str, *, api: Catalogue) -> PlaylistView:
    playlist, items = await asyncio.gather(
        api.get_playlist(uri), first(api.get_playlist_items(uri, limit=25))
    )

    return PlaylistView(playlist, items or ())


@dataclass(frozen=True, slots=True)
class Source:
    """One tab: how to search it, and (optionally) how to look a result up in full."""

    search: Callable[[str], AsyncGenerator[Sequence[Hit], None]]
    lookup: Callable[[str], Awaitable[object]] | None = None


def sources(api: Catalogue) -> dict[str, Source]:
    return {
        "Tracks": Source(api.search_tracks, partial(lookup_track, api=api)),
        "Artists": Source(api.search_artists, partial(lookup_artist, api=api)),
        "Albums": Source(api.search_albums, api.get_album),
        "Playlists": Source(api.search_playlists, partial(lookup_playlist, api=api)),
        "Podcasts": Source(api.search_podcasts, api.get_podcast),
        "Episodes": Source(api.search_episodes, api.get_podcast_episode),
        "Audiobooks": Source(api.search_audiobooks, api.get_audiobook),
        "People": Source(api.search_users, api.get_profile),
        "Authors": Source(api.search_authors),
        "Genres": Source(api.search_genres),
    }


@dataclass(slots=True)
class Feed:
    """A search's result stream plus everything it has produced so far."""

    stream: AsyncGenerator[Sequence[Hit], None]
    hits: list[Hit] = field(default_factory=list[Hit])
    busy: bool = False
    done: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def next_page(self) -> Sequence[Hit]:
        """Fetch the next page: empty if one is already in flight or none are left."""
        if self.busy or self.done:
            return ()

        async with self.lock:
            if self.done:
                return ()

            self.busy = True

            try:
                page = await anext(self.stream, None) or ()
            except Exception:
                self.done = True  # a stream that raised is finished
                raise
            finally:
                self.busy = False

            page = page[: MAX_RESULTS - len(self.hits)]

            self.hits.extend(page)

            self.done = not page or len(self.hits) >= MAX_RESULTS

            if self.done:
                await self.stream.aclose()

            return page

    async def close(self) -> None:
        async with self.lock:
            self.done = True

            await self.stream.aclose()


class Recent(dict[str, T]):
    """A dict that keeps only its newest `size` entries, so caches can't grow forever."""

    def __init__(self, size: int) -> None:
        super().__init__()

        self.size = size

    def __setitem__(self, key: str, value: T) -> None:
        super().__setitem__(key, value)

        if len(self) > self.size:
            del self[next(iter(self))]


def title(hit: Hit) -> str:
    return hit.name


def _row(hit: Hit) -> tuple[str, str, str, str]:
    if isinstance(hit, PlaylistTrack):
        bpm = f"{hit.bpm:.0f}" if hit.bpm is not None else ""

        return hit.name, bpm, hit.camelot_key or "", hit.uri

    return hit.name, "", "", hit.uri


def web_url(uri: str) -> str:
    """spotify:track:ID -> https://open.spotify.com/track/ID"""
    return "https://open.spotify.com/" + uri.removeprefix("spotify:").replace(":", "/")


def plain(value: object) -> object:
    """Use the standard dataclass export for copyable JSON."""
    return asdict(value) if is_dataclass(value) and not isinstance(value, type) else value


def decode(data: bytes) -> pil.Image:
    """Decode downloaded bytes. CPU work, so call it off the event loop."""
    with pil.open(BytesIO(data)) as original:
        image = original.convert("RGB")

        image.thumbnail((300, 300))

        return image


class CopyButton(
    Button, can_focus=False
):  # mouse-only: clicking never steals focus from the table
    """Copies the selected result's data as JSON."""

    def __init__(self) -> None:
        super().__init__("⧉ Copy data", compact=True, action="app.copy_data")


class Facts(Vertical):
    """A copy button above a scrollable description of the selected result."""

    DEFAULT_CSS = """
    Facts { padding: 0 2; border-left: tall $primary; }
    CopyButton { margin: 1 0; }
    """

    def compose(self) -> ComposeResult:
        yield CopyButton()

        with VerticalScroll():
            yield Static("[dim]↑ ↓ pick a result · enter to dive in[/]")

    def show(self, hit: Hit, data: Any) -> None:
        url = web_url(hit.uri)

        self.query_one(Static).update(
            Group(
                Text(title(hit), style=f"bold {GREEN}"),
                Text(url, style=f"underline link {url}"),
                Text(hit.uri, style="dim"),
                Rule(style="dim"),
                Pretty(data, expand_all=True),
            )
        )
        self.query_one(VerticalScroll).scroll_home(animate=False)


class DeepDive(ModalScreen[None]):
    """Artwork and a curated reading of the selected resource."""

    DEFAULT_CSS = """
    DeepDive { background: #0c1010; }
    DeepDive #detail-body { padding: 1 2; }
    DeepDive #gallery { width: 28; padding-right: 2; }
    DeepDive #reading { width: 1fr; padding: 0 2; border-left: solid #293c33; }
    DeepDive #kind { color: #1ED760; text-style: bold; margin-bottom: 1; }
    DeepDive #detail-title { text-style: bold; color: white; margin-bottom: 1; height: auto; }
    DeepDive #detail-content { height: auto; margin-top: 1; }
    DeepDive .slot { height: auto; margin-bottom: 2; }
    DeepDive .art-label { color: #a7b8ae; height: auto; margin-top: 1; }
    DeepDive .artwork { width: 24; height: 12; }
    DeepDive #detail-hint { height: 3; padding: 1; background: #17231d; text-align: center; color: #b7cbbf; }
    """
    BINDINGS = [
        Binding("escape,q", "app.pop_screen", "Back"),
        Binding("y", "app.copy_data", "Copy data"),
        Binding("c", "app.copy_uri", "Copy URI"),
        Binding("o", "app.open", "Open in browser"),
    ]

    def __init__(self, hit: Hit, data: Any, fetch: Callable[[str], Awaitable[pil.Image]]) -> None:
        super().__init__()

        self.hit, self.data, self.fetch = hit, data, fetch
        self.detail = present(hit.name, hit.uri, data)
        self.urls = [art.url for art in self.detail.artwork]

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="detail-body"):
            with VerticalScroll(id="gallery"):
                for art in self.detail.artwork:
                    with Vertical(classes="slot"):
                        yield Static(art.label, classes="art-label")

                if not self.urls:
                    yield Static("♫\n\nNo artwork available", classes="art-label")

            with VerticalScroll(id="reading"):
                yield Static(self.detail.kind.upper(), id="kind")
                yield Static(Text(self.detail.title), id="detail-title")
                yield Static(Text(self.hit.uri, style="dim"))
                yield Static(self.detail.content, id="detail-content")

        yield Static(
            "↑ ↓ Scroll   ·   Esc Back   ·   Y Copy JSON   ·   C Copy URI   ·   O Spotify",
            id="detail-hint",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = title(self.hit)

        self.query_one("#reading", VerticalScroll).focus()
        self.load_images()

    @work
    async def load_images(self) -> None:
        """Download every image at once; each appears the moment it's ready."""
        shown = await asyncio.gather(*map(self.paint, self.query(".slot"), self.urls))

        if failed := shown.count(False):
            self.notify(f"{failed} image(s) couldn't load", severity="warning")

    async def paint(self, slot: Widget, url: str) -> bool:
        try:
            await slot.mount(Image(await self.fetch(url), classes="artwork"), before=0)
        except Exception:
            return False

        return True


class Discover(App[None]):
    TITLE = "♫ SpotAPI"
    CSS = """
    Input { margin: 1 1 0 1; }
    TabbedContent, ContentSwitcher, TabPane, DataTable { height: 1fr; }
    TabbedContent { width: 3fr; }
    TabPane { padding: 0; }
    #side { width: 2fr; }
    #hint { height: 1; text-align: center; color: $text-muted; }
    """
    BINDINGS = [
        Binding("/", "focus('search')", "Search"),
        Binding("enter", "dive", "Dive in"),
        Binding("right", "tab(1)", "Switch tabs", priority=True),
        Binding("left", "tab(-1)", "Previous tab", show=False, priority=True),
        Binding("y", "copy_data", "Copy data"),
        Binding("c", "copy_uri", "Copy URI"),
        Binding("o", "open", "Open in browser"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, term: str) -> None:
        super().__init__()

        self.catalogue = Catalogue()
        self.sources = sources(self.catalogue)
        self.term = term
        self.took = 0.0  # seconds until every tab had its first page
        self.selected: Hit | None = None
        self.data: Any = None  # the selected result's full lookup, once it arrives
        self.feeds: dict[str, Feed] = {}
        self.cache = Recent[object](64)  # lookups by URI
        self.expanded = Recent[object](32)
        self.images = Recent[pil.Image](12)  # decoded images by URL
        self.http = httpx.AsyncClient(timeout=10, follow_redirects=True)
        self.tabs = TabbedContent()
        self.side = Facts(id="side")
        self.tables = {
            kind: DataTable[str](cursor_type="row", zebra_stripes=True) for kind in self.sources
        }

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Input(self.term, placeholder="Search Spotify…", id="search")

        with Horizontal():
            with self.tabs:
                for kind, table in self.tables.items():
                    with TabPane(kind, id=kind):
                        yield table

            yield self.side

        yield Static(
            "↑ ↓ Browse   ·   Enter Focused view   ·   / Search   ·   Y Copy JSON", id="hint"
        )
        yield Footer()

    async def on_mount(self) -> None:
        await self.catalogue.__aenter__()
        self.register_theme(SPOTIFY)

        self.theme = "spotify"

        for table in self.tables.values():
            table.add_columns("Name", "BPM", "Key", "URI")

        self.run_search(self.term)
        self.current()[1].focus()  # arrow keys work straight away

    async def on_unmount(self) -> None:
        try:
            await self.close_feeds()
        finally:
            await asyncio.gather(self.http.aclose(), self.catalogue.close())

        for image in self.images.values():
            image.close()

        self.images.clear()
        self.cache.clear()
        self.expanded.clear()

    def current(self) -> tuple[str, DataTable[str]]:
        """The visible tab's name and table."""
        return self.tabs.active, self.tables[self.tabs.active]

    def report_error(self, what: str, exc: Exception) -> None:
        self.notify(
            escape(f"{type(exc).__name__}: {exc}"),
            title=what,
            severity="error",
            timeout=8,
        )

    @work(exclusive=True, group="search")
    async def run_search(self, term: str) -> None:
        """Start every search at once and load each one's first page."""
        await self.close_feeds()

        started = perf_counter()
        self.term, self.took = term, 0.0
        self.selected, self.data = None, None

        if term.startswith(("https://", "http://", "spotify:")):
            self.feeds.clear()

            for table in self.tables.values():
                table.clear()

            await self.open_link(term)

            return

        self.feeds = {kind: Feed(source.search(term)) for kind, source in self.sources.items()}

        for table in self.tables.values():
            table.clear()

        await asyncio.gather(*(self.load_page(kind, feed) for kind, feed in self.feeds.items()))

        self.took = perf_counter() - started

        self.update_title()

    async def close_feeds(self) -> None:
        for worker in self.workers:
            if worker.group == "more":
                worker.cancel()

        feeds, self.feeds = self.feeds, {}

        await asyncio.gather(*(feed.close() for feed in feeds.values()))

    async def open_link(self, value: str) -> None:
        """Paste a resource link to inspect it directly."""
        try:
            resource = Public.parse_url(value)
            kinds = {
                "track": "Tracks",
                "artist": "Artists",
                "album": "Albums",
                "playlist": "Playlists",
                "show": "Podcasts",
                "episode": "Episodes",
                "user": "People",
            }

            if resource.kind not in kinds:
                raise ValueError("This link is not supported in the inspector")

            kind = kinds[resource.kind]
            getters: dict[str, Callable[[str], Awaitable[Hit]]] = {
                "track": self.catalogue.get_track,
                "album": self.catalogue.get_album,
                "artist": self.catalogue.get_artist,
                "playlist": self.catalogue.get_playlist,
                "show": self.catalogue.get_podcast,
                "episode": self.catalogue.get_podcast_episode,
                "user": self.catalogue.get_profile,
            }

            self.selected = await getters[resource.kind](resource.uri)

            self.data = plain(self.selected)

            self.side.show(self.selected, self.data)

            self.tabs.active = kind
            self.sub_title = resource.url

            if resource.kind == "playlist":
                self.tabs.active = "Tracks"
                feed = Feed(self.catalogue.get_playlist_tracks(resource.uri, limit=50))
                self.feeds["Tracks"] = feed

                await self.load_page("Tracks", feed)
                self.show_selected()
        except Exception as exc:
            self.report_error("Could not open Spotify link", exc)

    async def load_page(self, kind: str, feed: Feed) -> None:
        """Append a feed's next page to its table; failures become a toast."""
        table = self.tables[kind]
        table.loading = not feed.hits  # spinner only before the first page
        page: Sequence[Hit] = ()

        try:
            page = await feed.next_page()
        except Exception as exc:
            self.report_error(f"{kind} search failed", exc)
        finally:
            table.loading = False

        if self.feeds.get(kind) is not feed:  # a newer search replaced this one
            return

        table.add_rows(_row(hit) for hit in page)

        count = f"{len(feed.hits)}{'' if feed.done else '+'}"
        self.tabs.get_tab(kind).label = Text(f"{kind} · {count}")

        self.update_title()

        if page:
            self.prefetch(kind)

    def prefetch(self, kind: str) -> None:
        """Load the next page when the cursor nears the end of a table."""
        feed = self.feeds.get(kind)

        if (
            feed
            and feed.hits
            and not feed.done
            and self.tables[kind].cursor_row >= len(feed.hits) - PREFETCH
        ):
            self.run_worker(self.load_page(kind, feed), group="more")

    def update_title(self) -> None:
        total = sum(len(feed.hits) for feed in self.feeds.values())
        timing = f" · first page in {self.took:.2f}s" if self.took else ""
        self.sub_title = f"“{self.term}” · {total:,} results{timing}"

    @on(Input.Submitted)
    def submit(self, event: Input.Submitted) -> None:
        if term := event.value.strip():
            self.run_search(term)
            self.current()[1].focus()

    async def lookup(self, kind: str, hit: Hit) -> Any:
        """Everything about a hit as plain data (cached). Raises if the lookup fails."""
        if (data := self.cache.get(hit.uri)) is None:
            fetch = self.sources[kind].lookup
            self.cache[hit.uri] = data = plain(await fetch(hit.uri) if fetch else hit)

        return data

    async def detail(self, kind: str, hit: Hit) -> Any:
        """Like lookup(), but a failure becomes a toast and the search hit stands in."""
        try:
            return await self.lookup(kind, hit)
        except Exception as exc:
            self.report_error(f"{kind} lookup failed", exc)

            return plain(hit)

    @on(DataTable.RowHighlighted)
    @on(TabbedContent.TabActivated)
    def show_selected(self) -> None:
        """Show the highlighted row's details and keep its table topped up."""
        kind, table = self.current()

        self.prefetch(kind)

        feed = self.feeds.get(kind)
        hits = feed.hits if feed else []

        if 0 <= table.cursor_row < len(hits) and hits[table.cursor_row] is not self.selected:
            self.selected, self.data = hits[table.cursor_row], None

            self.load_detail(kind, self.selected)

    @work(exclusive=True, group="detail")
    async def load_detail(self, kind: str, hit: Hit) -> None:
        if hit.uri not in self.cache:
            await asyncio.sleep(DEBOUNCE)  # skip rows the cursor is only passing over

            self.side.loading = True

        try:
            data = await self.detail(kind, hit)

            if self.selected is hit:
                self.data = data

                self.side.show(hit, data)
        finally:
            if self.selected is hit:
                self.side.loading = False

    @on(DataTable.RowSelected)
    def action_dive(self) -> None:
        """Open the full-screen view of the selected result."""
        if self.selected is not None:
            self.open_dive(self.current()[0], self.selected)

    @work(exclusive=True, group="dive")
    async def open_dive(self, kind: str, hit: Hit) -> None:
        data = self.expanded.get(hit.uri)

        if data is None:
            data = await self.detail(kind, hit)

            if kind == "Tracks":
                data = await self.expand_track(data)

            self.expanded[hit.uri] = data

        self.data = data

        await self.push_screen(DeepDive(hit, self.data, self.fetch_image))

    async def expand_track(self, payload: object) -> object:
        data = dict(node(payload))
        track = at(data, "track")
        artists = items(at(track, "first_artist").get("items"))
        artist_uri = artists[0].get("uri") if artists else None
        album_uri = at(track, "album_of_track").get("uri")

        async def add(key: str, uri: object, fetch: Callable[[str], Awaitable[object]]) -> None:
            if isinstance(uri, str) and uri:
                try:
                    data[key] = plain(await fetch(uri))
                except Exception as exc:
                    self.report_error(f"Could not load {key} context", exc)

        await asyncio.gather(
            add("artist", artist_uri, self.catalogue.get_artist),
            add("album", album_uri, self.catalogue.get_album),
        )

        return data

    async def fetch_image(self, url: str) -> pil.Image:
        """Download and decode an image once; the event loop stays free throughout."""
        if (image := self.images.get(url)) is None:
            response = await self.http.get(url)

            response.raise_for_status()

            self.images[url] = image = await asyncio.to_thread(decode, response.content)

        return image

    def check_action(self, action: str, parameters: tuple[object, ...]) -> bool:
        """Leave ← → to the search box, and to nobody while a deep dive is open."""
        if action == "tab":
            return not isinstance(self.focused, Input) and not isinstance(self.screen, DeepDive)

        return True

    def action_tab(self, step: int) -> None:
        kinds = list(self.sources)
        self.tabs.active = kinds[(kinds.index(self.tabs.active) + step) % len(kinds)]

        self.current()[1].focus()

    def action_open(self) -> None:
        if self.selected is not None and not webbrowser.open(web_url(self.selected.uri)):
            self.notify("Couldn't open a browser", severity="warning")

    def action_copy_uri(self) -> None:
        if self.selected is not None:
            self.copy_to_clipboard(self.selected.uri)
            self.notify(self.selected.uri, title="Copied URI")

    def action_copy_data(self) -> None:
        if self.data is None:
            self.notify("Still loading, try again in a moment", severity="warning")

            return

        text = json.dumps(self.data, indent=2, default=str, ensure_ascii=False)

        self.copy_to_clipboard(text)
        self.notify(f"{len(text):,} characters of JSON", title="Copied data")


if __name__ == "__main__":
    Discover(" ".join(sys.argv[1:]) or random.choice(SUGGESTIONS)).run()
