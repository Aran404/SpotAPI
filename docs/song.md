# Song Class

The `Song` class provides methods to interact with songs in the context of a playlist and allows for operations such as searching, adding, removing, and liking songs.

## Parameters

- **playlist**: `PrivatePlaylist | None`  
  An optional instance of `PrivatePlaylist`. If not provided, the client is used directly.

- **client**: `TLSClient`  
  The client used for making HTTP requests. Defaults to a new `TLSClient` instance with certain parameters.

- **language**: `str`, optional  
  The language for API responses using ISO 639-1 language codes (e.g., 'ko', 'ja', 'zh', 'en'). Default is 'en'.

## Methods

### `__init__(self, playlist: PrivatePlaylist | None = None, *, client: TLSClient = TLSClient("chrome_120", "", auto_retries=3), language: str = "en") -> None`
Initializes the `Song` class with an optional `PrivatePlaylist` instance and a `TLSClient` instance.

- **Raises:**  
  `ValueError` if no playlist is provided and no client is set.

## Language Support Examples

```python
from spotapi import Song

# Initialize with Korean language
song_ko = Song(language="ko")

# Search for songs with Korean responses
results = song_ko.query_songs("BTS", limit=20)

# Change language at runtime
song_ko.base.set_language("ja")  # Switch to Japanese
```

### `get_track_info(self, track_id: str) -> Mapping[str, Any]`
Searches for songs in the Spotify catalog.

- **Args:**
  - `track_id`: `str`  
    The ID of the song. Not the URI.

- **Returns:**  
  `Mapping[str, Any]`  
  The raw track result.

- **Raises:**  
  `SongError` if there is an issue retrieving the song or if the response is invalid.

### `query_songs(self, query: str, /, limit: int = 10, *, offset: int = 0) -> Mapping[str, Any]`
Searches for songs in the Spotify catalog.

- **Args:**
  - `query`: `str`  
    The search query.
  - `limit`: `int`  
    The maximum number of results to return. Default is 10.
  - `offset`: `int`  
    The offset for pagination. Default is 0.

- **Returns:**  
  `Mapping[str, Any]`  
  The raw search result.

- **Raises:**  
  `SongError` if there is an issue retrieving the songs or if the response is invalid.

### `paginate_songs(self, query: str, /) -> Generator[Mapping[str, Any], None, None]`
Generator that fetches songs in chunks.

- **Args:**
  - `query`: `str`  
    The search query.

- **Returns:**  
  `Generator[Mapping[str, Any], None, None]`  
  A generator yielding song results in chunks.

### `add_song_to_playlist(self, song_id: str, /) -> None`
Adds a song to the playlist.

- **Args:**
  - `song_id`: `str`  
    The ID of the song to add.

- **Raises:**  
  `ValueError` if no playlist is set or if the song ID is invalid.  
  `SongError` if there is an issue adding the song.

### `remove_song_from_playlist(
    self,
    *,
    all_instances: bool = False,
    uid: str | None = None,
    song_id: str | None = None,
    song_name: str | None = None
) -> None`
Removes a song from the playlist.

- **Args:**
  - `all_instances`: `bool`  
    If `True`, removes all instances of the song. Only `song_name` can be used in this case.
  - `uid`: `str | None`  
    The unique ID of the song to remove.
  - `song_id`: `str | None`  
    The ID of the song to remove.
  - `song_name`: `str | None`  
    The name of the song to remove.

- **Raises:**  
  `ValueError` if no valid song ID, name, or UID is provided, or if both `song_id` and `all_instances` are provided.  
  `SongError` if the song is not found in the playlist.

### `like_song(self, song_id: str, /) -> None`
Likes a song.

- **Args:**
  - `song_id`: `str`  
    The ID of the song to like.

- **Raises:**  
  `ValueError` if no playlist is set or if the song ID is invalid.  
  `SongError` if there is an issue liking the song.