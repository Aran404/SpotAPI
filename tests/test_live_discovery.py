"""Anonymous radio, recommendation and Canvas contracts."""

import pytest

from spotapi import Catalogue

pytestmark = [pytest.mark.live]


async def test_live_discovery() -> None:
    async with Catalogue() as catalogue:
        for seed in (
            "spotify:track:33XUHrCbrAW6me9ewdCZip",
            "spotify:artist:66CXWjxzNUsdJxJ2JdwvnR",
            "spotify:album:4aawyAB9vmqN3uQ7FjRGTy",
        ):
            radio = await catalogue.get_radio(seed)
            assert radio is not None and radio.kind == "playlist"

        tracks = await catalogue.get_playlist_recommendations("37i9dQZF1DXcBWIGoYBM5M", limit=3)
        assert len(tracks) == 3
        assert all(track.id and track.uri and track.name for track in tracks)
        canvases = await catalogue.get_canvases(["33XUHrCbrAW6me9ewdCZip"])
        assert all(canvas.url and canvas.track_uri for canvas in canvases)


async def test_live_artist_discovered_on() -> None:
    async with Catalogue() as catalogue:
        playlists = await catalogue.get_artist_discovered_on("4tZwfgrHOc3mvqYlEYSvVi")
    assert playlists
    assert any(playlist is not None for playlist in playlists)
    assert all(
        playlist is None or (playlist.name and playlist.uri.startswith("spotify:playlist:"))
        for playlist in playlists
    )
