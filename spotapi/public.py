"""One-shot catalogue operations with automatic resource ownership."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable, Sequence
from contextlib import aclosing
from typing import Literal, TypeVar, overload

from spotapi.models.discovery import Canvas, RecommendedTrack

from .batch import BatchItem
from .catalogue import Catalogue, SpotifyItem
from .charts import Chart, list_charts
from .datastruct import ObjectDict
from .embeds import Embed, get_embed
from .models import (
    Album,
    AlbumDetails,
    AlbumTrack,
    Artist,
    ArtistDetails,
    ArtistRelatedArtist,
    ArtistRelease,
    ArtistTopTrack,
    Audiobook,
    Author,
    Episode,
    Genre,
    Playlist,
    PlaylistDetails,
    PlaylistEntry,
    PlaylistTrack,
    Podcast,
    PodcastDetails,
    PodcastEpisodeDetails,
    PublicProfile,
    SearchResults,
    Track,
    TrackCredits,
    TrackDetails,
    User,
)
from .models.catalogue.entities import AudiobookChapter
from .models.discovery import Concert, CoverColors
from .operations import (
    DEFAULT_SEARCH_TYPES,
    Operations,
    ResourceInputKind,
    SearchInputKind,
    SearchOptions,
)
from .resources import SpotifyResource, parse_spotify_resource

__all__ = (
    "Public",
    "SearchResults",
    "SpotifyResource",
)

_ResultT = TypeVar("_ResultT")


class Public:
    """Read public Spotify data without an API key or an explicit client.

    Await single-result methods directly. Iterate page methods with
    ``async for``; their ``limit`` controls page size, not the total result
    count. Each call owns an anonymous catalogue and closes it before returning
    or when its stream finishes. Use ``contextlib.aclosing`` when stopping a
    stream early. Reuse :class:`Catalogue` for several related operations.

    Example::

        hits = await Public.search("Daft Punk", types="track", limit=5)
        for track in hits.tracks:
            print(track.name, track.uri)
    """

    __slots__ = ()

    @staticmethod
    def parse_url(value: str, /, *, kind: ResourceInputKind | None = None) -> SpotifyResource:
        """Normalize a Spotify URL, URI, or typed ID."""
        return parse_spotify_resource(value, kind)

    @staticmethod
    async def get(
        value: str, /, *, kind: ResourceInputKind | None = None, language: str | None = None
    ) -> SpotifyItem:
        """Fetch a Spotify resource from its URL, URI, or typed ID."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get(value, kind=kind)

    @staticmethod
    @overload
    async def get_resource(uri: str, operation: Operations, /) -> ObjectDict: ...

    @staticmethod
    @overload
    async def get_resource(
        uri: str, operation: Operations, typ: type[_ResultT], /
    ) -> _ResultT: ...

    @staticmethod
    async def get_resource(
        uri: str, operation: Operations, typ: type[_ResultT] | None = None, /
    ) -> ObjectDict | _ResultT:
        """Execute a specific resource operation."""
        async with Catalogue() as catalogue:
            if typ is None:
                return await catalogue.get_resource(uri, operation)

            return await catalogue.get_resource(uri, operation, typ)

    @staticmethod
    async def search(
        query: str,
        /,
        *,
        types: SearchInputKind | Iterable[SearchInputKind] = DEFAULT_SEARCH_TYPES,
        options: SearchOptions | None = None,
        limit: int | None = None,
        language: str | None = None,
    ) -> SearchResults:
        """Search public categories and close the session before returning.

        Args:
            query: Nonempty search text.
            types: Category or categories; defaults to tracks, artists, albums,
                playlists and podcasts. Singular and plural names are accepted.
            options: Advanced Spotify inclusion options.
            limit: Maximum results per category, from 1 to 100. Overrides
                ``options.limit``; defaults to 20 without options.
            language: Optional language or locale, such as ``fr-CA``.

        Returns:
            Typed hits grouped by category, with empty tuples for categories
            that were not requested or returned no usable results.

        Raises:
            ValueError: Search text, categories, limit or language are invalid.
            SpotAPIError: Authentication, transport or response parsing fails.
        """
        async with Catalogue(language=language) as catalogue:
            return await catalogue.search(query, types=types, options=options, limit=limit)

    @staticmethod
    async def search_typed(
        typ: type[_ResultT],
        operation: Operations,
        query: str,
        /,
        *,
        options: SearchOptions | None = None,
    ) -> AsyncGenerator[Sequence[_ResultT], None]:
        """Stream typed result pages for a single persisted search operation."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_typed(typ, operation, query, options=options)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_tracks(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Track], None]:
        """Stream typed pages of matching tracks.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available tracks in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_tracks(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_albums(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Album], None]:
        """Stream typed pages of matching albums.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available albums in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_albums(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_artists(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Artist], None]:
        """Stream typed pages of matching artists.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available artists in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_artists(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_playlists(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Playlist], None]:
        """Stream typed pages of matching playlists.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available playlists in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_playlists(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_podcasts(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Podcast], None]:
        """Stream typed pages of matching podcasts.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available podcasts in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_podcasts(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_episodes(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Episode], None]:
        """Stream typed pages of matching episodes.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available episodes in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_episodes(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_audiobooks(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Audiobook], None]:
        """Stream typed pages of matching audiobooks.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available audiobooks in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_audiobooks(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_users(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[User], None]:
        """Stream typed pages of matching users.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available users in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_users(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_authors(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Author], None]:
        """Stream typed pages of matching authors.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available authors in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_authors(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_genres(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Genre], None]:
        """Stream typed pages of matching genres.

        Args:
            query: Nonempty search text.
            limit: Page size from 1 to 100; this does not cap the total results.

        Yields:
            One page of available genres in Spotify's result order.

        Note:
            Use ``contextlib.aclosing`` if iteration may stop early. Argument
            or request errors can surface when iteration begins.
        """
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.search_genres(query, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def iter_tracks(query: str, /) -> AsyncGenerator[Track, None]:
        """Yield tracks individually, hiding search-page boundaries."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.iter_tracks(query)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def iter_albums(query: str, /) -> AsyncGenerator[Album, None]:
        """Yield albums individually, hiding search-page boundaries."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.iter_albums(query)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def iter_artists(query: str, /) -> AsyncGenerator[Artist, None]:
        """Yield artists individually, hiding search-page boundaries."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.iter_artists(query)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def iter_playlists(query: str, /) -> AsyncGenerator[Playlist, None]:
        """Yield playlists individually, hiding search-page boundaries."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.iter_playlists(query)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def iter_podcasts(query: str, /) -> AsyncGenerator[Podcast, None]:
        """Yield podcast shows individually, hiding search-page boundaries."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.iter_podcasts(query)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def get_playlist(uri: str, /, *, language: str | None = None) -> PlaylistDetails:
        """Read public playlist metadata from a URL, URI, or ID."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_playlist(uri)

    @staticmethod
    async def get_playlist_items(
        uri: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[PlaylistEntry], None]:
        """Page through tracks, episodes and unavailable occurrences in source order."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.get_playlist_items(uri, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def iter_playlist_items(
        uri: str, /, *, limit: int = 100
    ) -> AsyncGenerator[PlaylistEntry, None]:
        """Yield playlist occurrences individually, preserving duplicate songs."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.iter_playlist_items(uri, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def get_playlist_tracks(
        uri: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[PlaylistTrack], None]:
        """Page through available music tracks, including optional BPM and musical keys."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.get_playlist_tracks(uri, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def get_album_tracks(
        uri: str, /, *, limit: int = 50
    ) -> AsyncGenerator[Sequence[AlbumTrack], None]:
        """Read every album track in disc/track order, including albums over one page."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.get_album_tracks(uri, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def get_related_artists(
        uri: str, /, *, language: str | None = None
    ) -> tuple[ArtistRelatedArtist, ...]:
        """Explore the related artists shown on a public artist profile."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_related_artists(uri)

    @staticmethod
    async def get_artist_releases(
        uri: str,
        /,
        *,
        kind: Literal["all", "albums", "singles", "compilations"] = "all",
        limit: int = 50,
    ) -> AsyncGenerator[Sequence[ArtistRelease], None]:
        """Page through an artist's releases, newest first, flattening release groups."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.get_artist_releases(uri, kind=kind, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def get_radio(seed: str, *, language: str | None = None) -> SpotifyResource | None:
        """Resolve track, artist or album radio using a self-cleaning anonymous session."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_radio(seed)

    @staticmethod
    async def get_playlist_recommendations(
        value: str, *, limit: int = 20, skip: Iterable[str] = ()
    ) -> tuple[RecommendedTrack, ...]:
        """Read suggested playlist tracks without login or library changes."""
        async with Catalogue() as catalogue:
            return await catalogue.get_playlist_recommendations(value, limit=limit, skip=skip)

    @staticmethod
    async def get_canvas(track: str) -> Canvas | None:
        """Read one available Canvas record; return None when it is unavailable."""
        async with Catalogue() as catalogue:
            return await catalogue.get_canvas(track)

    @staticmethod
    async def get_canvases(tracks: Sequence[str]) -> tuple[Canvas, ...]:
        """Batch up to 50 Canvas lookups and close the owned session afterward."""
        async with Catalogue() as catalogue:
            return await catalogue.get_canvases(tracks)

    @staticmethod
    async def get_track_credits(uri: str, /, *, language: str | None = None) -> TrackCredits:
        """Discover the performers, writers and producers credited on a song."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_track_credits(uri)

    @staticmethod
    async def get_artist_top_tracks(uri: str, /) -> tuple[ArtistTopTrack, ...]:
        """Read Spotify's public top-track selection and play counts for an artist."""
        async with Catalogue() as catalogue:
            return await catalogue.get_artist_top_tracks(uri)

    @staticmethod
    async def get_profile(
        value: str, /, *, limit: int = 20, language: str | None = None
    ) -> PublicProfile:
        """Read a public user's profile and first public playlists; no login needed."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_profile(value, limit=limit)

    @staticmethod
    async def get_artist(uri: str, /, *, language: str | None = None) -> ArtistDetails:
        """Fetch an artist profile and overview by Spotify URL, URI, or ID."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_artist(uri)

    @staticmethod
    async def get_album(uri: str, /, *, language: str | None = None) -> AlbumDetails:
        """Fetch album metadata and track information."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_album(uri)

    @staticmethod
    async def get_track(uri: str, /, *, language: str | None = None) -> TrackDetails:
        """Fetch track metadata by Spotify URL, URI, or ID."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_track(uri)

    @staticmethod
    async def get_tracks(
        tracks: Sequence[str], /, *, language: str | None = None
    ) -> tuple[TrackDetails, ...]:
        """Fetch several tracks in input order using one client."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_tracks(tracks)

    @staticmethod
    async def get_albums(
        albums: Sequence[str], /, *, language: str | None = None
    ) -> tuple[AlbumDetails, ...]:
        """Fetch several albums in input order using one client."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_albums(albums)

    @staticmethod
    async def get_artists(
        artists: Sequence[str], /, *, language: str | None = None
    ) -> tuple[ArtistDetails, ...]:
        """Fetch several artists in input order using one client."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_artists(artists)

    @staticmethod
    async def get_podcast(uri: str, /, *, language: str | None = None) -> PodcastDetails:
        """Read podcast metadata from a URL, URI, or bare show ID."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_podcast(uri)

    @staticmethod
    async def get_audiobook(uri: str, /, *, language: str | None = None) -> Audiobook:
        """Read audiobook metadata from its Spotify show link, URI or ID."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_audiobook(uri)

    @staticmethod
    async def get_audiobook_chapters(
        uri: str, /, *, limit: int = 50
    ) -> AsyncGenerator[Sequence[AudiobookChapter], None]:
        """Stream chapters from an audiobook available in the current market."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.get_audiobook_chapters(uri, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def get_podcast_episode(
        uri: str, /, *, language: str | None = None
    ) -> PodcastEpisodeDetails:
        """Fetch a podcast episode by Spotify URL, URI, or ID."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_podcast_episode(uri)

    @staticmethod
    async def get_podcast_episodes(
        uri: str, /, *, limit: int = 50
    ) -> AsyncGenerator[Sequence[PodcastEpisodeDetails], None]:
        """Stream a show's episodes in pages."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.get_podcast_episodes(uri, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def iter_podcast_episodes(
        uri: str, /, *, limit: int = 50
    ) -> AsyncGenerator[PodcastEpisodeDetails, None]:
        """Yield a show's episodes individually, hiding pagination details."""
        async with (
            Catalogue() as catalogue,
            aclosing(catalogue.iter_podcast_episodes(uri, limit=limit)) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    def list_charts() -> tuple[Chart, ...]:
        """List editorial playlist shortcuts without creating a client."""
        return list_charts()

    @staticmethod
    async def get_chart(key: str, *, language: str | None = None) -> PlaylistDetails:
        """Read an editorial playlist's metadata by its chart shortcut."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_chart(key)

    @staticmethod
    async def get_similar_albums(
        track: str, *, limit: int = 10, language: str | None = None
    ) -> tuple[Album, ...]:
        """Recommend albums from a track using one automatically closed scope."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_similar_albums(track, limit=limit)

    @staticmethod
    async def get_artist_discovered_on(
        artist: str, /, *, language: str | None = None
    ) -> tuple[Playlist | None, ...]:
        """Read discovery playlists, retaining unavailable slots as None."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_artist_discovered_on(artist)

    @staticmethod
    async def get_artist_events(
        artist: str, *, language: str | None = None
    ) -> tuple[Concert, ...]:
        """Read an artist's upcoming concerts in the current request region."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_artist_events(artist)

    @staticmethod
    async def get_colors(image: str, *, language: str | None = None) -> CoverColors:
        """Extract a Spotify image palette using one automatically closed scope."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.get_colors(image)

    @staticmethod
    async def fetch_many(
        values: Sequence[str],
        *,
        concurrency: int = 8,
        kind: ResourceInputKind | None = None,
        language: str | None = None,
    ) -> tuple[BatchItem[SpotifyItem], ...]:
        """Read mixed URLs/URIs, keeping per-input failures instead of aborting."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.fetch_many(values, kind=kind, concurrency=concurrency)

    @staticmethod
    async def get_embed(
        value: str, *, kind: ResourceInputKind | None = None, browser: bool = False
    ) -> Embed:
        """Read public embed metadata, optionally using the Playwright browser extra."""
        return await get_embed(value, kind=kind, browser=browser)

    @staticmethod
    async def lookup(
        value: str, *, kind: ResourceInputKind | None = None, fallback: bool = True
    ) -> SpotifyItem | Embed:
        """Read rich catalogue details with an explicitly typed public embed fallback."""
        async with Catalogue() as catalogue:
            return await catalogue.lookup(value, kind=kind, fallback=fallback)
