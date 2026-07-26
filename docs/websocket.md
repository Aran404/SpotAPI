# WebsocketStreamer Class

The `WebsocketStreamer` class provides functionality to connect and interact with Spotify's websocket API.

## Parameters

- **login**: `Login`  
  The `Login` instance for the user. The user must be logged in for this class to function.

## Methods

### `__init__(self, login: Login) -> None`
Initializes the `WebsocketStreamer` with a `Login` instance and sets up the websocket connection.

- **Raises:**  
  `ValueError` if the user is not logged in.

### `register_device(self) -> None`
Registers the device with Spotify.

### `connect_device(self) -> dict[str, Any]`
Connects the device to Spotify and returns the response.

- **Returns:**  
  `dict[str, Any]`  
  A dictionary containing the response from Spotify.

- **Raises:**  
  `WebSocketError` if there is an issue connecting the device.