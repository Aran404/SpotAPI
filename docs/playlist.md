# PublicPlaylist Class

The `PublicPlaylist` class allows you to access public information about a Spotify playlist without requiring user login.

## Parameters

- **playlist**: `str`  
  The Spotify URI of the playlist, it is used to initialize the playlist.

- **client**: `TLSClient`  
  An instance of `TLSClient` used for making HTTP requests. Defaults to a new instance with specified parameters.

- **language**: `str`, optional  
  The language for API responses using ISO 639-1 language codes (e.g., 'ko', 'ja', 'zh', 'en'). Default is 'en'.

## Methods

### `__init__(self, playlist: str | None = None, /, *, client: TLSClient = TLSClient("chrome_120", "", auto_retries=3), language: str = "en") -> None`
Initializes the `PublicPlaylist` class with an optional playlist URI and a `TLSClient` instance.

## Language Support Examples

```python
from spotapi import PublicPlaylist

# Initialize with Korean language
playlist = PublicPlaylist("37i9dQZF1DXcBWIGoYBM5M", language="ko")

# Get playlist info with Korean language responses
info = playlist.get_playlist_info()

# Change language at runtime
playlist.base.set_language("ja")  # Switch to Japanese
```

### `get_playlist_info(self, limit: int = 25, *, offset: int = 0) -> Mapping[str, Any]`
Fetches public information about the playlist.

- **Args:**
  - `limit`: `int`  
    The maximum number of results to return. Default is 25.
  - `offset`: `int`  
    The offset for pagination. Default is 0.

- **Returns:**  
  `Mapping[str, Any]`  
  The playlist information.

- **Raises:**  
  `PlaylistError` if there is an issue retrieving the playlist information or if the response is invalid.

### `paginate_playlist(self) -> Generator[Mapping[str, Any], None, None]`
Generator that fetches playlist information in chunks.

- **Returns:**  
  `Generator[Mapping[str, Any], None, None]`  
  A generator yielding playlist information in chunks.

- **Note:** If the total number of tracks is 343 or fewer, pagination is not required.

---

# PrivatePlaylist Class

The `PrivatePlaylist` class allows you to interact with a playlist while logged in, enabling operations such as adding to and removing from the library, creating, and getting recommendations.

## Parameters

- **login**: `Login`  
  The login object used for authenticated requests.

- **playlist**: `str | None`  
  The Spotify URI of the playlist. If provided, it is used to initialize the playlist.

## Methods

### `__init__(self, login: Login, playlist: str | None = None) -> None`
Initializes the `PrivatePlaylist` class with a `Login` object and an optional playlist URI.

- **Raises:**  
  `ValueError` if not logged in or if playlist ID cannot be extracted from the provided URI.

### `set_playlist(self, playlist: str) -> None`
Sets or updates the playlist ID.

- **Args:**
  - `playlist`: `str`  
    The Spotify URI or ID of the playlist to set.

- **Raises:**  
  `ValueError` if the playlist URI is invalid.

### `add_to_library(self) -> None`
Adds the playlist to the user's library.

- **Raises:**  
  `ValueError` if the playlist ID is not set.  
  `PlaylistError` if there is an issue adding the playlist.

### `remove_from_library(self) -> None`
Removes the playlist from the user's library.

- **Raises:**  
  `ValueError` if the playlist ID is not set.  
  `PlaylistError` if there is an issue removing the playlist.

### `delete_playlist(self) -> None`
Deletes the playlist from the user's library. This is the same as removing it from the library.

- **Raises:**  
  `ValueError` if the playlist ID is not set.  
  `PlaylistError` if there is an issue deleting the playlist.

### `get_library(self, limit: int = 50, /) -> Mapping[str, Any]`
Fetches all playlists in the user's library.

- **Args:**
  - `limit`: `int`  
    The maximum number of playlists to return. Default is 50.

- **Returns:**  
  `Mapping[str, Any]`  
  The user's library information.

- **Raises:**  
  `PlaylistError` if there is an issue retrieving the library information.

### `create_playlist(self, name: str) -> str`
Creates a new playlist.

- **Args:**
  - `name`: `str`  
    The name of the new playlist.

- **Returns:**  
  `str`  
  The URI of the newly created playlist.

- **Raises:**  
  `PlaylistError` if there is an issue creating the playlist.

### `recommended_songs(self, num_songs: int = 20) -> Mapping[str, Any]`
Fetches recommended songs for the playlist.

- **Args:**
  - `num_songs`: `int`  
    The number of recommended songs to fetch. Default is 20.

- **Returns:**  
  `Mapping[str, Any]`  
  The recommended songs.

- **Raises:**  
  `PlaylistError` if there is an issue retrieving recommended songs.