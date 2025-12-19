# Artist Class

The `Artist` class represents an artist in the Spotify catalog, providing methods to interact with the Spotify API for artist-related queries and actions.

## Parameters

- **login**: `Optional[Login]`, optional  
  A logged-in `Login` object. Required for certain methods. If not provided, some methods will raise a `ValueError`.
  
- **client**: `TLSClient`, optional  
  A `TLSClient` used for making requests to the API. If not provided, a default one will be used.

- **language**: `str`, optional  
  The language for API responses using ISO 639-1 language codes (e.g., 'ko', 'ja', 'zh', 'en'). Default is 'en'.

## Methods

### `__init__(self, login: Login | None = None, *, client: TLSClient = TLSClient("chrome_120", "", auto_retries=3), language: str = "en") -> None`
Initializes the `Artist` class. If a `Login` object is provided, it checks if the user is logged in. If not, a `ValueError` is raised.

### `set_language(self, language: str) -> None`
Changes the language for API requests at runtime.

- **Parameters:**
  - `language`: ISO 639-1 language code (e.g., 'ko', 'ja', 'zh', 'en').

## Language Support Examples

```python
from spotapi import Artist

# Initialize with Korean language
artist_ko = Artist(language="ko")

# Change language at runtime
artist_ko.base.set_language("ja")  # Switch to Japanese

# Query artist with Japanese responses
results = artist_ko.get_artist("4tZwfgrHOc3mvqYlEYSvVi")
```

### `query_artists(self, query: str, /, limit: int = 10, *, offset: int = 0) -> Mapping[str, Any]`
Searches for an artist in the Spotify catalog.

- **Parameters:**
  - `query`: The search term for the artist.
  - `limit`: The maximum number of results to return (default is 10).
  - `offset`: The offset from where to start fetching results (default is 0).
  
- **Returns:** A mapping of the search results.

### `get_artist(self, artist_id: str, /, *, locale_code: str = "en") -> Mapping[str, Any]`
Fetches detailed information about an artist by ID.

- **Parameters:**
  - `artist_id`: The Spotify artist ID. Both raw IDs and URIs (`artist:xxxxx`) are accepted.
  - `locale_code`: Locale used for language-specific content (default `"en"`).

- **Returns:** A mapping containing the artist overview.

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
