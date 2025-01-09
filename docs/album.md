# PublicAlbum Class

The `PublicAlbum` class allows you to access public information about a Spotify album without requiring user login.

## Parameters

- **album**: `str`  
  The Spotify URI of the album,  it is used to initialize the album.

- **client**: `TLSClient`  
  An instance of `TLSClient` used for making HTTP requests. Defaults to a new instance with specified parameters.

## Methods

### `__init__(self, album: str, /, *, client: TLSClient = TLSClient("chrome_120", "", auto_retries=3)) -> None`
Initializes the `PublicAlbum` class with an optional album URI and a `TLSClient` instance.

### `get_album_info(self, limit: int = 25, *, offset: int = 0) -> Mapping[str, Any]`
Fetches public information about the album.

- **Args:**
  - `limit`: `int`  
    The maximum number of results to return. Default is 25.
  - `offset`: `int`  
    The offset for pagination. Default is 0.

- **Returns:**  
  `Mapping[str, Any]`  
  The album information.

- **Raises:**  
  `AlbumError` if there is an issue retrieving the album information or if the response is invalid.

### `paginate_album(self) -> Generator[Mapping[str, Any], None, None]`
Generator that fetches album information in chunks.

- **Returns:**  
  `Generator[Mapping[str, Any], None, None]`  
  A generator yielding album information in chunks.

- **Note:** If the total number of tracks is 343 or fewer, pagination is not required.