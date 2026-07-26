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

### `get_artist_discography(self, artist_id: str, /, *, section: Literal["all", "albums", "singles", "compilations"] = "all", offset: int = 0, limit: int = 50, order: Literal["DATE_DESC", "DATE_ASC"] = "DATE_DESC") -> Mapping[str, Any]`
Fetches an artist's discography (releases) with pagination. Unlike `get_artist` (which uses `queryArtistOverview` and caps each section at ~10 items), this method targets the dedicated discography operations that support proper `offset`/`limit`/`order`.

- **Parameters:**
  - `artist_id`: The Spotify artist ID. Both raw IDs and URIs (`artist:xxxxx` or `spotify:artist:xxxxx`) are accepted.
  - `section`: Which release group to fetch.
    - `"all"` (default): merged albums + singles + compilations sorted by date.
    - `"albums"` / `"singles"` / `"compilations"`: only that release type.
  - `offset`: Pagination offset (default `0`).
  - `limit`: Items per page (default `50`).
  - `order`: Sort order — `"DATE_DESC"` (newest first, default) or `"DATE_ASC"`.

- **Returns:** A mapping containing the discography page. Items live under `data.artistUnion.discography.<section>.items` with the section's `totalCount`.

- **Note:** The API does not enforce a strict cap on `limit`; values up to 1000+ have been observed to work. The default of 50 mirrors `paginate_artist_discography`'s page size.

### `paginate_artist_discography(self, artist_id: str, /, *, section: Literal["all", "albums", "singles", "compilations"] = "all", order: Literal["DATE_DESC", "DATE_ASC"] = "DATE_DESC") -> Generator[Mapping[str, Any], None, None]`
Generates an artist's discography in chunks of 50 items per page until `totalCount` is reached.

- **Parameters:**
  - `artist_id`: The Spotify artist ID (raw ID or URI).
  - `section`: Same as `get_artist_discography`.
  - `order`: Same as `get_artist_discography`.

- **Yields:** Lists of release items per page. Each item carries a nested `releases.items[*]` with the actual release `id`, `name`, `date`, `type`, `coverArt`, etc.

- **Note:** If the section's total count is ≤ 50, only one page is yielded.

### `follow(self, artist_id: str, /) -> None`
Follows an artist on Spotify.

- **Parameters:**
  - `artist_id`: The ID of the artist to follow.

### `unfollow(self, artist_id: str, /) -> None`
Unfollows an artist on Spotify.

- **Parameters:**
  - `artist_id`: The ID of the artist to unfollow.
