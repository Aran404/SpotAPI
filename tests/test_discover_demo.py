"""The optional demo should cover the catalogue without needing network access."""

import asyncio
from functools import partial
from io import StringIO
from unittest.mock import AsyncMock, Mock, patch

import pytest

pytest.importorskip("textual")
pytest.importorskip("textual_image")
pytest.importorskip("httpx")

# The image renderer probes the real terminal during import. Headless tests
# must not read terminal replies through pytest's captured stdin.
with patch("sys.__stdout__", StringIO()):
    from spotapi._demo import discover

from spotapi.models import Track


async def test_shutdown_releases_images_even_when_a_feed_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = discover.Discover("Example")
    image = Mock(spec=discover.pil.Image)
    app.images["cover"] = image
    app.cache["track"] = object()
    app.expanded["track"] = object()
    close_catalogue = AsyncMock()
    monkeypatch.setattr(discover.Catalogue, "close", close_catalogue)
    monkeypatch.setattr(app, "close_feeds", AsyncMock(side_effect=RuntimeError("feed failed")))

    with pytest.raises(RuntimeError, match="feed failed"):
        await app.on_unmount()

    assert app.http.is_closed
    close_catalogue.assert_awaited_once()
    image.close.assert_called_once()
    assert not app.images
    assert not app.cache
    assert not app.expanded


@pytest.fixture(autouse=True)
def offline_image_transport(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep headless demo tests independent of proxy configuration and network access."""

    def unexpected_request(request: discover.httpx.Request) -> discover.httpx.Response:
        raise AssertionError(f"Unexpected image request in an offline test: {request.url.host}")

    factory = partial(
        discover.httpx.AsyncClient,
        transport=discover.httpx.MockTransport(unexpected_request),
        trust_env=False,
    )
    monkeypatch.setattr(discover.httpx, "AsyncClient", factory)


async def test_ten_tabs_render_and_finish_their_feeds(monkeypatch: pytest.MonkeyPatch) -> None:
    async def search(term: str):
        yield [Track(id="track", name="Example", uri="spotify:track:track")]

    sources = {name: discover.Source(search) for name in discover.sources(discover.Catalogue())}

    monkeypatch.setattr(discover, "sources", Mock(return_value=sources))

    app = discover.Discover("Example")

    async with app.run_test(size=(150, 44)) as pilot:
        await pilot.pause()

        async with asyncio.timeout(5):
            while app.workers:
                await pilot.pause()

        assert len(app.tables) == 10
        assert all(table.row_count == 1 for table in app.tables.values())
        assert "Example" in app.export_screenshot()


@pytest.mark.parametrize("key", ("escape", "down"))
async def test_search_can_return_to_results_without_a_mouse(
    monkeypatch: pytest.MonkeyPatch, key: str
) -> None:
    async def search(term: str):
        yield [Track(id="track", name="Example", uri="spotify:track:track")]

    monkeypatch.setattr(
        discover, "sources", Mock(return_value={"Tracks": discover.Source(search)})
    )
    app = discover.Discover("Example")
    async with app.run_test(size=(130, 42)) as pilot:
        await pilot.pause()
        search_box = app.query_one("#search", discover.SearchInput)
        search_box.focus()
        await pilot.pause()
        assert app.focused is search_box
        await pilot.press(key)
        assert app.focused is app.tables["Tracks"]


def test_playlist_rows_show_optional_bpm_and_keys() -> None:
    from spotapi.models import PlaylistTrack
    from spotapi.models.catalogue import from_dict

    track = from_dict(
        PlaylistTrack,
        {
            "name": "Song",
            "uri": "spotify:track:track",
            "playlistAudioAttributes": {
                "bpm": 128,
                "key": {"camelotKey": {"value": "12B"}},
            },
        },
    )

    assert discover._row(track) == ("Song", "128", "12B", "spotify:track:track")


async def test_enter_shows_curated_details_and_only_relevant_artwork(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hit = Track(id="track", name="Example", uri="spotify:track:track")
    payload = {
        "track": {
            "name": hit.name,
            "album_of_track": {
                "name": "An album",
                "cover_art": {"sources": [{"url": "cover", "width": 300}]},
            },
            "first_artist": {
                "items": [
                    {
                        "profile": {"name": "An artist"},
                        "visuals": {"avatar_image": {"sources": [{"url": "portrait"}]}},
                        "related_content": {"sources": [{"url": "unrelated"}]},
                    }
                ]
            },
        },
        "credits": {"contributors": [{"name": "A composer", "role": "Composer"}]},
        "artist": {"stats": {"monthly_listeners": 1000000}},
        "album": {"tracks_v2": {"items": [{"track": {"name": "Albumcut"}}]}},
    }
    downloaded: list[str] = []

    async def search(term: str):
        yield [hit]

    async def lookup(uri: str) -> object:
        return payload

    async def fetch(url: str) -> discover.pil.Image:
        downloaded.append(url)

        return discover.pil.new("RGB", (100, 100), "green")

    monkeypatch.setattr(
        discover, "sources", Mock(return_value={"Tracks": discover.Source(search, lookup)})
    )

    app = discover.Discover("Example")

    monkeypatch.setattr(app, "fetch_image", fetch)

    async with app.run_test(size=(130, 42)) as pilot:
        await pilot.pause()

        async with asyncio.timeout(5):
            while app.workers:
                await pilot.pause()

        app.tables["Tracks"].focus()
        await pilot.press("enter")
        await pilot.pause()

        async with asyncio.timeout(5):
            while app.workers:
                await pilot.pause()

        assert isinstance(app.screen, discover.DeepDive)
        assert app.focused is app.screen.query_one("#reading")
        assert downloaded == ["cover", "portrait"]
        assert len(app.screen.query(discover.Image)) == 2
        assert all(image.region.height > 0 for image in app.screen.query(discover.Image))
        assert not app.screen.query(discover.Facts)
        assert "A&#160;composer" in app.export_screenshot()
        assert "Albumcut" in app.export_screenshot()
        assert "1,000,000" in app.export_screenshot()
        assert app.screen.query_one("#detail-hint", discover.Static)

        await pilot.press("escape")

        assert not isinstance(app.screen, discover.DeepDive)
