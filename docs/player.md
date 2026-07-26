# Player Class

**Description**:  
A class designed to control the Spotify player API without requiring a Spotify Premium account.\
**NOTE**: Only works at the moment if you dump your own cookies. Find out how to import cookies [HERE](../README.md/#import-cookies)

## Methods:

### `__init__(self, login: Login, device_id: str | None = None) -> None`

**Description**:  
Initializes the `Player` class and sets up the player to interact with the specified device or active device.

**Parameters**:
- **`login (Login)`**: The login instance used for authentication.
- **`device_id (str, optional)`**: The device ID to connect to for the player. If not provided, it will use the active device.
- **`use_active_device (bool)`**: If True, the player will use the active device.

**Example**:
```python
login_instance = Login(username, password)
player = Player(login_instance)
```

### `transfer_player(self, from_device_id: str, to_device_id: str) -> None`

**Description**:  
Transfers the player streamer from one device to another.

**Parameters**:
- **`from_device_id (str)`**: The device ID to transfer from.
- **`to_device_id (str)`**: The device ID to transfer to.

**Example**:
```python
player.transfer_player("device_1", "device_2")
```

### `run_command(self, from_device_id: str, to_device_id: str, command: str) -> None`

**Description**:  
Sends a generic command to the player.

**Parameters**:
- **`from_device_id (str)`**: The device ID to send the command from.
- **`to_device_id (str)`**: The device ID to send the command to.
- **`command (str)`**: The command to send.

**Example**:
```python
player.run_command("device_1", "device_2", "pause")
```

### `seek_to(self, position_ms: int, /) -> None`

**Description**:  
Seeks to a specific position in the player.

**Parameters**:
- **`position_ms (int)`**: The position in milliseconds to seek to.

**Example**:
```python
player.seek_to(30000)
```

### `restart_song(self) -> None`

**Description**:  
Restarts the current song.

**Example**:
```python
player.restart_song()
```

### `pause(self) -> None`

**Description**:  
Pauses the player.

**Example**:
```python
player.pause()
```

### `resume(self) -> None`

**Description**:  
Resumes the player.

**Example**:
```python
player.resume()
```

### `skip_next(self) -> None`

**Description**:  
Skips to the next track.

**Example**:
```python
player.skip_next()
```

### `skip_prev(self) -> None`

**Description**:  
Skips to the previous track.

**Example**:
```python
player.skip_prev()
```

### `add_to_queue(self, track: str, /) -> None`

**Description**:  
Adds a track to the player's queue.

**Parameters**:
- **`track (str)`**: The track URI to add to the queue.

**Example**:
```python
player.add_to_queue("spotify:track:6rqhFgbbKwnb9MLmUQDhG6")
```

### `play_track(self, track: str, playlist: str, /) -> None`

**Description**:  
Overrides the player with a new track.

**Parameters**:
- **`track (str)`**: The track URI to play.
- **`playlist (str)`**: The playlist URI to play the track from.

**Example**:
```python
player.play_track("spotify:track:6rqhFgbbKwnb9MLmUQDhG6", "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M")
```

### `repeat_track(self, value: bool, /) -> None`

**Description**:  
Repeats the current track.

**Parameters**:
- **`value (bool)`**: Whether to repeat the track or disable repeating.

**Example**:
```python
player.repeat_track(True)
```

### `set_volume(self, volume_percent: float, /) -> None`

**Description**:  
Sets the volume of the player.

**Parameters**:
- **`volume_percent (float)`**: The volume to set the player to. Must be a percent representation between 0.0 and 1.0.

**Example**:
```python
player.set_volume(0.5)
```

### `fade_in_volume(self, volume_percent: float, /, duration_ms: int = 500, *, request_time_ms: int | None = None) -> None`

**Description**:  
Slowly increases or decreases the volume of the player.

**Parameters**:
- **`volume_percent (float)`**: The target volume to set the player to. Must be between 0.0 and 1.0.
- **`duration_ms (int)`**: The duration of the fade-in in milliseconds. Defaults to 500ms.
- **`request_time_ms (int, optional)`**: If not None, it will account for the request time in the `duration_ms`.

**Example**:
```python
player.fade_in_volume(0.7, duration_ms=1000)
```
