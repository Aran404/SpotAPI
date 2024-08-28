import pytest
from spotapi import PrivatePlaylist, PlaylistError
from spotapi._tests.features.session import _MainFixture

PUBLIC_PLAYLIST_URI = "40GMAhriYJRO1rsY4YdrZb"
login_instance = _MainFixture.login
playlist_instance = PrivatePlaylist(login=login_instance, playlist=PUBLIC_PLAYLIST_URI)


def test_private_playlist_initialization():
    """Test initialization of the PrivatePlaylist class."""
    private_playlist = PrivatePlaylist(
        login=login_instance, playlist=PUBLIC_PLAYLIST_URI
    )
    assert private_playlist.playlist_id == "40GMAhriYJRO1rsY4YdrZb"
    assert private_playlist._playlist is True


def test_set_playlist():
    """Test set_playlist method."""
    private_playlist = PrivatePlaylist(login=login_instance)
    private_playlist.set_playlist(PUBLIC_PLAYLIST_URI)
    assert private_playlist.playlist_id == "40GMAhriYJRO1rsY4YdrZb"
    assert private_playlist._playlist is True


def test_add_to_library():
    """Test add_to_library method."""
    try:
        playlist_instance.add_to_library()
    except PlaylistError as e:
        pytest.fail(f"add_to_library method raised an error: {e}")


def test_remove_from_library():
    """Test remove_from_library method."""
    try:
        playlist_instance.remove_from_library()
    except PlaylistError as e:
        pytest.fail(f"remove_from_library method raised an error: {e}")


def test_create_playlist():
    """Test create_playlist method."""
    try:
        playlist_id = playlist_instance.create_playlist(name="Test Playlist")
        assert playlist_id.startswith("spotify:playlist:")
    except PlaylistError as e:
        pytest.fail(f"create_playlist method raised an error: {e}")


def test_get_library():
    """Test get_library method."""
    try:
        library = playlist_instance.get_library(5)
        assert "data" in library
        assert isinstance(library["data"], dict)
    except PlaylistError as e:
        pytest.fail(f"get_library method raised an error: {e}")


def test_recommended_songs():
    """Test recommended_songs method."""
    try:
        recommendations = playlist_instance.recommended_songs(num_songs=5)
        assert "tracks" in recommendations
        assert isinstance(recommendations["tracks"], list)
        assert len(recommendations["tracks"]) == 5
    except PlaylistError as e:
        pytest.fail(f"recommended_songs method raised an error: {e}")
