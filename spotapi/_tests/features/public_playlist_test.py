import pytest
from spotapi import PublicPlaylist, PlaylistError
from spotapi._tests.features.session import _MainFixture

PUBLIC_PLAYLIST_URI = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"
playlist_instance = PublicPlaylist(PUBLIC_PLAYLIST_URI)


def test_public_playlist_initialization():
    """Test initialization of the PublicPlaylist class."""
    playlist_with_uri = PublicPlaylist(PUBLIC_PLAYLIST_URI)
    assert playlist_with_uri.playlist_id == "37i9dQZF1DXcBWIGoYBM5M"
    assert (
        playlist_with_uri.playlist_link
        == f"https://open.spotify.com/playlist/{playlist_with_uri.playlist_id}"
    )


def test_get_playlist_info():
    """Test get_playlist_info method."""
    info = playlist_instance.get_playlist_info(limit=5)
    assert "data" in info
    assert "playlistV2" in info["data"]
    assert "content" in info["data"]["playlistV2"]
    assert isinstance(info["data"]["playlistV2"]["content"], dict)


def test_paginate_playlist():
    """Test paginate_playlist method for proper pagination."""
    pages = list(playlist_instance.paginate_playlist())
    assert isinstance(pages, list)
    assert len(pages) > 0
    for page in pages:
        assert isinstance(page, dict)
