# Artist Class

The `Artist` class represents an artist in the Spotify catalog, providing methods to interact with the Spotify API for artist-related queries and actions.

## Parameters

- **login**: `Optional[Login]`, optional  
  A logged-in `Login` object. Required for certain methods. If not provided, some methods will raise a `ValueError`.
  
- **client**: `TLSClient`, optional  
  A `TLSClient` used for making requests to the API. If not provided, a default one will be used.

## Methods

### `__init__(self, login: Login | None = None, *, client: TLSClient = TLSClient("chrome_120", "", auto_retries=3)) -> None`
Initializes the `Artist` class. If a `Login` object is provided, it checks if the user is logged in. If not, a `ValueError` is raised.

### `query_artists(self, query: str, /, limit: int = 10, *, offset: int = 0) -> Mapping[str, Any]`
Searches for an artist in the Spotify catalog.

- **Parameters:**
  - `query`: The search term for the artist.
  - `limit`: The maximum number of results to return (default is 10).
  - `offset`: The offset from where to start fetching results (default is 0).
  
- **Returns:** A mapping of the search results.

### `paginate_artists(self, query: str, /) -> Generator[Mapping[str, Any], None, None]`
Generates artist data in chunks.

- **Parameters:**
  - `query`: The search term for the artist.
  
- **Yields:** A generator of artist data chunks.

### `follow(self, artist_id: str, /) -> None`
Follows an artist on Spotify.

- **Parameters:**
  - `artist_id`: The ID of the artist to follow.

### `unfollow(self, artist_id: str, /) -> None`
Unfollows an artist on Spotify.

- **Parameters:**
  - `artist_id`: The ID of the artist to unfollow.
