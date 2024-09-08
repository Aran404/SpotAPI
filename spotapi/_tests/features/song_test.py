import pytest
from spotapi import Song, SongError, PrivatePlaylist
from session import _MainFixture

playlist_instance = PrivatePlaylist(_MainFixture.login, playlist="test_playlist_id")
song_instance = Song(playlist=playlist_instance)


def test_song_initialization():
    """Test the initialization of the Song class."""
    song_with_playlist = Song(
        playlist=playlist_instance, client=_MainFixture.login.client
    )
    assert song_with_playlist.playlist is playlist_instance
    assert isinstance(
        song_with_playlist.base.client, _MainFixture.login.client.__class__
    )


def test_query_songs():
    """Test the query_songs method for valid response structure."""
    response = song_instance.query_songs("ariana", limit=2)

    assert "data" in response
    assert "searchV2" in response["data"]
    assert "tracksV2" in response["data"]["searchV2"]
    assert "items" in response["data"]["searchV2"]["tracksV2"]
    assert isinstance(response["data"]["searchV2"]["tracksV2"]["items"], list)
    assert len(response["data"]["searchV2"]["tracksV2"]["items"]) > 0


def test_paginate_songs():
    """Test the paginate_songs method for proper pagination."""
    query = "ariana"
    results = list(song_instance.paginate_songs(query))

    assert isinstance(results, list)
    assert len(results) > 0
    for chunk in results:
        assert isinstance(chunk, list)


def test_add_song_to_playlist():
    """Test the add_song_to_playlist method."""
    song_id = "1zi7xx7UVEFkmKfv06H8x0"
    try:
        song_instance.add_song_to_playlist(song_id)
    except SongError as e:
        pytest.fail(f"Add song to playlist method raised an error: {e}")


def test_remove_song_from_playlist():
    """Test the remove_song_from_playlist method."""
    song_id = "1zi7xx7UVEFkmKfv06H8x0"
    try:
        song_instance.remove_song_from_playlist(song_id=song_id)
    except SongError as e:
        pytest.fail(f"Remove song from playlist method raised an error: {e}")


def test_like_song():
    """Test the like_song method."""
    song_id = "1zi7xx7UVEFkmKfv06H8x0"
    try:
        song_instance.like_song(song_id)
    except SongError as e:
        pytest.fail(f"Like song method raised an error: {e}")
