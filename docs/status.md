# PlayerStatus Class

The `PlayerStatus` class provides information about the current state of the Spotify player. It includes methods for accessing player state, device IDs, and queue information.

## Parameters

- **login**: `Login`  
  The login instance used for authentication.

- **s_device_id**: `Optional[str]`  
  The device ID to use for the player. If `None`, a new device ID will be generated.

## Methods

### `__init__(self, login: Login, s_device_id: str | None = None) -> None`
Initializes the `PlayerStatus` class with a login instance and optional device ID.

- **Args:**
  - `login`: `Login`  
    The login instance for authentication.
  - `s_device_id`: `Optional[str]`  
    The device ID for the player (optional).

### `renew_state(self) -> None`
Refreshes the current state and device information from the Spotify API.

### `saved_state(self) -> PlayerState`
Gets the last saved state of the player.

- **Returns:**  
  `PlayerState`  
  The last saved state of the player.

- **Raises:**  
  `ValueError` if the player state could not be retrieved.

### `state(self) -> PlayerState`
Gets the current state of the player.

- **Returns:**  
  `PlayerState`  
  The current state of the player.

- **Raises:**  
  `ValueError` if the player state could not be retrieved.

### `saved_device_ids(self) -> Devices`
Gets the last saved device IDs of the player.

- **Returns:**  
  `Devices`  
  The last saved device IDs.

- **Raises:**  
  `ValueError` if the devices could not be retrieved or the active device ID is missing.

### `device_ids(self) -> Devices`
Gets the current device IDs of the player.

- **Returns:**  
  `Devices`  
  The current device IDs.

- **Raises:**  
  `ValueError` if the devices could not be retrieved.

### `active_device_id(self) -> str`
Gets the active device ID of the player.

- **Returns:**  
  `str`  
  The active device ID.

- **Raises:**  
  `ValueError` if the active device ID could not be retrieved.

### `next_song_in_queue(self) -> Track | None`
Gets the next song in the queue.

- **Returns:**  
  `Track | None`  
  The next song in the queue or `None` if the queue is empty.

### `next_songs_in_queue(self) -> List[Track]`
Gets the next songs in the queue.

- **Returns:**  
  `List[Track]`  
  The list of next songs in the queue.

### `last_played(self) -> Track | None`
Gets the last played track.

- **Returns:**  
  `Track | None`  
  The last played track or `None` if no tracks have been played.

### `last_songs_played(self) -> List[Track]`
Gets the last played songs.

- **Returns:**  
  `List[Track]`  
  The list of last played songs.

---

# EventManager Class

The `EventManager` class extends `PlayerStatus` and adds functionality for subscribing to and managing events from the Spotify websocket.

## Parameters

- **login**: `Login`  
  The login instance used for authentication.

- **s_device_id**: `Optional[str]`  
  The device ID to use for the player. If `None`, a new device ID will be generated.

## Methods

### `__init__(self, login: Login, s_device_id: str | None = None) -> None`
Initializes the `EventManager` class, sets up the websocket listener, and starts it in a separate thread.

- **Args:**
  - `login`: `Login`  
    The login instance for authentication.
  - `s_device_id`: `Optional[str]`  
    The device ID for the player (optional).

### `subscribe(self, event: str) -> Callable[..., Any]`
Decorator to subscribe a function to a Spotify websocket event.

- **Args:**
  - `event`: `str`  
    The event to subscribe to.

- **Returns:**  
  `Callable[..., Any]`  
  The decorated function.

### `unsubscribe(self, event: str, func: Callable[..., Any]) -> None`
Unsubscribes a function from an event.

- **Args:**
  - `event`: `str`  
    The event to unsubscribe from.
  - `func`: `Callable[..., Any]`  
    The function to unsubscribe.