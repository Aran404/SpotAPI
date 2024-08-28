import pytest
from spotapi import Player, PlayerError, Login
from spotapi._tests.features.session import _MainFixture

player_instance = Player(login=_MainFixture.login)


def test_player_initialization():
    """Test the initialization of the Player class."""
    player_with_login = Player(login=_MainFixture.login)
    assert player_with_login.active_id is not None
    assert player_with_login.device_id is not None


def test_seek_to():
    """Test the seek_to method."""
    position_ms = 60000

    try:
        player_instance.seek_to(position_ms)
    except PlayerError as e:
        pytest.fail(f"Seek to method raised an error: {e}")


def test_set_shuffle():
    """Test the set_shuffle method."""
    try:
        player_instance.set_shuffle(True)
    except PlayerError as e:
        pytest.fail(f"Set shuffle method raised an error: {e}")


def test_set_volume():
    """Test the set_volume method."""
    volume_percent = 0.5  # 50%

    try:
        player_instance.set_volume(volume_percent)
    except PlayerError as e:
        pytest.fail(f"Set volume method raised an error: {e}")


def test_fade_in_volume():
    """Test the fade_in_volume method."""
    volume_percent = 0.5  # 50%
    duration_ms = 1000  # 1 second

    try:
        player_instance.fade_in_volume(volume_percent, duration_ms)
    except PlayerError as e:
        pytest.fail(f"Fade in volume method raised an error: {e}")


def test_play_track():
    """Test the play_track method."""
    track = "spotify:track:3TVXtAsR1Inumwj472S9r4"
    playlist = "spotify:playlist:3oMgjZftIhf6akplUUPx3y"

    try:
        player_instance.play_track(track, playlist)
    except PlayerError as e:
        pytest.fail(f"Play track method raised an error: {e}")


def test_repeat_track():
    """Test the repeat_track method."""
    try:
        player_instance.repeat_track(True)
    except PlayerError as e:
        pytest.fail(f"Repeat track method raised an error: {e}")


def test_add_to_queue():
    """Test the add_to_queue method."""
    track = "spotify:track:3TVXtAsR1Inumwj472S9r4"

    try:
        player_instance.add_to_queue(track)
    except PlayerError as e:
        pytest.fail(f"Add to queue method raised an error: {e}")


def test_pause():
    """Test the pause method."""
    try:
        player_instance.pause()
    except PlayerError as e:
        pytest.fail(f"Pause method raised an error: {e}")


def test_resume():
    """Test the resume method."""
    try:
        player_instance.resume()
    except PlayerError as e:
        pytest.fail(f"Resume method raised an error: {e}")


def test_skip_next():
    """Test the skip_next method."""
    try:
        player_instance.skip_next()
    except PlayerError as e:
        pytest.fail(f"Skip next method raised an error: {e}")


def test_skip_prev():
    """Test the skip_prev method."""
    try:
        player_instance.skip_prev()
    except PlayerError as e:
        pytest.fail(f"Skip prev method raised an error: {e}")
