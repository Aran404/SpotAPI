# Language Support

SpotAPI now supports multiple languages for API responses through the `Accept-Language` header. This allows you to receive localized content from Spotify's API in your preferred language.

## Supported Features

- **ISO 639-1 Language Codes**: Use standard two-letter language codes like 'ko', 'ja', 'zh', 'en'
- **Runtime Language Changes**: Switch languages during execution without reinitializing objects
- **All Classes Supported**: Available in all major SpotAPI classes

## Supported Classes

All major SpotAPI classes now support the `language` parameter:

- `Artist`
- `Song` 
- `PublicPlaylist`
- `PrivatePlaylist`
- `PublicAlbum`
- `Podcast`

## Usage Examples

### Initialize with Language

```python
from spotapi import Artist, Song, PublicPlaylist, PublicAlbum

# Initialize with Korean language
artist = Artist(language="ko")
song = Song(language="ko") 
playlist = PublicPlaylist("37i9dQZF1DXcBWIGoYBM5M", language="ko")
album = PublicAlbum("4m2880jivSbbyEGAKfITCa", language="ko")
```

### Change Language at Runtime

```python
from spotapi import Artist

# Start with English
artist = Artist(language="en")

# Switch to Japanese
artist.base.set_language("ja")

# Switch to Korean
artist.base.set_language("ko")
```

### Common Language Codes

| Code | Language |
|------|----------|
| `en` | English (default) |
| `ko` | Korean |
| `ja` | Japanese |
| `zh` | Chinese |
| `es` | Spanish |
| `fr` | French |
| `de` | German |
| `pt` | Portuguese |

## Implementation Details

- Language setting is applied at the `BaseClient` level
- The `Accept-Language` header is automatically added to all API requests
- Default language is English (`en`)
- Language changes apply to all subsequent API calls
- No breaking changes - existing code continues to work with default English

## Example: Multi-Language Search

```python
from spotapi import Song

# Search in Korean
song_ko = Song(language="ko")
korean_results = song_ko.query_songs("BTS")

# Search in Japanese  
song_ja = Song(language="ja")
japanese_results = song_ja.query_songs("BTS")

# Search in English
song_en = Song(language="en")
english_results = song_en.query_songs("BTS")
```

This feature ensures that SpotAPI can provide localized experiences for users worldwide.