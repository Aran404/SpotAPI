from spotapi import PlayerStatus
from spotapi.types.data import PlayerState, Devices, Track
from session import _MainFixture


def test_player_status_initialization():
    """Test the initialization of the PlayerStatus class."""
    player_status = PlayerStatus(login=_MainFixture.login)
    assert player_status.client == _MainFixture.login.client
    assert player_status._device_dump is None
    assert player_status._state is None
    assert player_status._devices is None

    device_id = "some_device_id"
    player_status_with_device = PlayerStatus(
        login=_MainFixture.login, s_device_id=device_id
    )
    assert player_status_with_device.device_id == device_id


def test_renew_state():
    """Test the renew_state method."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    assert player_status._device_dump is not None
    assert player_status._state is not None
    assert player_status._devices is not None


def test_saved_state():
    """Test the saved_state property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    assert isinstance(player_status.saved_state, PlayerState)
    assert player_status._state
    assert player_status.saved_state == PlayerState.from_dict(player_status._state)


def test_state():
    """Test the state property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    assert isinstance(player_status.state, PlayerState)
    assert player_status._state
    assert player_status.state == PlayerState.from_dict(player_status._state)


def test_saved_device_ids():
    """Test the saved_device_ids property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    assert isinstance(player_status.saved_device_ids, Devices)
    assert player_status._device_dump
    assert (
        player_status.saved_device_ids.active_device_id
        == player_status._device_dump["active_device_id"]
    )


def test_device_ids():
    """Test the device_ids property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    assert isinstance(player_status.device_ids, Devices)
    assert player_status._device_dump
    assert (
        player_status.device_ids.active_device_id
        == player_status._device_dump["active_device_id"]
    )


def test_active_device_id():
    """Test the active_device_id property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    assert player_status._device_dump
    assert (
        player_status.active_device_id == player_status._device_dump["active_device_id"]
    )


def test_next_song_in_queue():
    """Test the next_song_in_queue property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    next_song = player_status.next_song_in_queue
    if len(player_status.state.next_tracks) > 0:
        assert isinstance(next_song, Track)
    else:
        assert next_song is None


def test_next_songs_in_queue():
    """Test the next_songs_in_queue property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    next_songs = player_status.next_songs_in_queue
    assert isinstance(next_songs, list)
    if len(player_status.state.next_tracks) > 0:
        assert isinstance(next_songs[0], Track)


def test_last_played():
    """Test the last_played property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    last_played = player_status.last_played
    if len(player_status.state.prev_tracks) > 0:
        assert isinstance(last_played, Track)
    else:
        assert last_played is None


def test_last_songs_played():
    """Test the last_songs_played property."""
    player_status = PlayerStatus(login=_MainFixture.login)
    player_status.renew_state()

    last_songs = player_status.last_songs_played
    assert isinstance(last_songs, list)
    if len(player_status.state.prev_tracks) > 0:
        assert isinstance(last_songs[0], Track)
