# Public Class Documentation

The `Public` class provides static methods for accessing public information from Spotify. It serves as a high-level interface for fetching data about artists, albums, playlists, songs, and podcasts without requiring user authentication or any underlying client management.

## Features
- Simplified access to Spotify's public information.
- Uses a client pool for efficient memory management of HTTP clients.
- Handles data fetching with pagination where applicable.

---

## Methods

### `artist_search(query: str, /) -> GeneratorType`
Searches for artists matching a query.

- **Args:**
  - `query`: `str`  
    The search query for the artist.

- **Returns:**  
  `GeneratorType`  
  A generator yielding artist information in paginated chunks.

- **Usage Example:**  
  ```python
  for artist in Public.artist_search("The Beatles"):
      print(artist)
  ```

---

### `album_info(album_id: str, /) -> GeneratorType`
Fetches public information about an album using its Spotify ID.

- **Args:**
  - `album_id`: `str`  
    The Spotify ID of the album.

- **Returns:**  
  `GeneratorType`  
  A generator yielding album information in paginated chunks.

- **Usage Example:**  
  ```python
  for album in Public.album_info("5U4W9E5WsYb2jUQWePT8Xm"):
      print(album)
  ```

---

### `playlist_info(playlist_id: str, /) -> GeneratorType`
Fetches public information about a playlist using its Spotify ID.

- **Args:**
  - `playlist_id`: `str`  
    The Spotify ID of the playlist.

- **Returns:**  
  `GeneratorType`  
  A generator yielding playlist information in paginated chunks.

- **Usage Example:**  
  ```python
  for playlist in Public.playlist_info("37i9dQZF1DXcBWIGoYBM5M"):
      print(playlist)
  ```

---

### `song_search(query: str, /) -> GeneratorType`
Searches for songs matching a query.

- **Args:**
  - `query`: `str`  
    The search query for the song.

- **Returns:**  
  `GeneratorType`  
  A generator yielding song information in paginated chunks.

- **Usage Example:**  
  ```python
  for song in Public.song_search("Bohemian Rhapsody"):
      print(song)
  ```

---

### `song_info(song_id: str, /) -> Mapping[str, Any]`
Fetches detailed information about a specific song using its Spotify ID.

- **Args:**
  - `song_id`: `str`  
    The Spotify ID of the song.

- **Returns:**  
  `Mapping[str, Any]`  
  A dictionary containing detailed song information.

- **Usage Example:**  
  ```python
  song = Public.song_info("7hQJA50XrCWABAu5v6QZ4i")
  print(song)
  ```

---

### `podcast_info(podcast_id: str, /) -> GeneratorType`
Fetches public information about a podcast using its Spotify ID.

- **Args:**
  - `podcast_id`: `str`  
    The Spotify ID of the podcast.

- **Returns:**  
  `GeneratorType`  
  A generator yielding podcast information in paginated chunks.

- **Usage Example:**  
  ```python
  for podcast in Public.podcast_info("4rOoJ6Egrf8K2IrywzwOMk"):
      print(podcast)
  ```

---

### `podcast_episode_info(episode_id: str, /) -> Mapping[str, Any]`
Fetches detailed information about a specific podcast episode using its Spotify ID.

- **Args:**
  - `episode_id`: `str`  
    The Spotify ID of the episode.

- **Returns:**  
  `Mapping[str, Any]`  
  A dictionary containing detailed episode information.

- **Usage Example:**  
  ```python
  episode = Public.podcast_episode_info("1HpkG1StJQsNN09awYFTB3")
  print(episode)
  ```