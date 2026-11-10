"""One-shot catalogue operations with automatic resource ownership."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Iterable, Sequence
from contextlib import aclosing
from typing import Literal, TypeVar, overload

from .catalogue import (
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
    Catalogue,
    Episode,
    Genre,
    InclusionParameters,
    Operations,
    Playlist,
    PlaylistDetails,
    PlaylistEntry,
    PlaylistTrack,
    Podcast,
    PodcastDetails,
    PodcastEpisodeDetails,
    PublicProfile,
    ResourceInputKind,
    SearchInputKind,
    SearchResults,
    SpotifyItem,
    SpotifyResource,
    Track,
    TrackCredits,
    TrackDetails,
    User,
    parse_spotify_resource,
)
from .datastruct import ObjectDict
from .discovery import Canvas, RecommendedTrack
from .operations import DEFAULT_SEARCH_TYPES

__all__ = ("Public", "SearchResults", "SpotifyResource")

_ResultT = TypeVar("_ResultT")


class Public:
    """Use one catalogue operation without managing a client yourself."""

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
        parameters: InclusionParameters | None = None,
        limit: int | None = None,
        language: str | None = None,
    ) -> SearchResults:
        """Search selected categories in one request."""
        async with Catalogue(language=language) as catalogue:
            return await catalogue.search(query, types=types, parameters=parameters, limit=limit)

    @staticmethod
    async def search_typed(
        typ: type[_ResultT],
        operation: Operations,
        query: str,
        /,
        *,
        parameters: InclusionParameters | None = None,
    ) -> AsyncGenerator[Sequence[_ResultT], None]:
        """Stream typed result pages for a single persisted search operation."""
        async with (
            Catalogue() as catalogue,
            aclosing(
                catalogue.search_typed(typ, operation, query, parameters=parameters)
            ) as pages,
        ):
            async for page in pages:
                yield page

    @staticmethod
    async def search_tracks(
        query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Track], None]:
        """Stream typed pages of matching tracks."""
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
        """Stream typed pages of matching albums."""
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
        """Stream typed pages of matching artists."""
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
        """Stream typed pages of matching playlists."""
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
        """Stream typed pages of matching podcasts."""
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
        """Stream typed pages of matching episodes."""
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
        """Stream typed pages of matching audiobooks."""
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
        """Stream typed pages of matching users."""
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
        """Stream typed pages of matching authors."""
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
        """Stream typed pages of matching genres."""
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
    async def get_playlist(uri: str, /) -> PlaylistDetails:
        """Read public playlist metadata from a URL, URI, or ID."""
        async with Catalogue() as catalogue:
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
    async def get_related_artists(uri: str, /) -> tuple[ArtistRelatedArtist, ...]:
        """Explore the related artists shown on a public artist profile."""
        async with Catalogue() as catalogue:
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
    async def get_radio(seed: str) -> SpotifyResource | None:
        """Resolve track, artist or album radio using a self-cleaning anonymous session."""
        async with Catalogue() as catalogue:
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
    async def get_track_credits(uri: str, /) -> TrackCredits:
        """Discover the performers, writers and producers credited on a song."""
        async with Catalogue() as catalogue:
            return await catalogue.get_track_credits(uri)

    @staticmethod
    async def get_artist_top_tracks(uri: str, /) -> tuple[ArtistTopTrack, ...]:
        """Read Spotify's public top-track selection and play counts for an artist."""
        async with Catalogue() as catalogue:
            return await catalogue.get_artist_top_tracks(uri)

    @staticmethod
    async def get_profile(value: str, /, *, limit: int = 20) -> PublicProfile:
        """Read a public user's profile and first public playlists; no login needed."""
        async with Catalogue() as catalogue:
            return await catalogue.get_profile(value, limit=limit)

    @staticmethod
    async def get_artist(uri: str, /) -> ArtistDetails:
        """Fetch an artist profile and overview by Spotify URL, URI, or ID."""
        async with Catalogue() as catalogue:
            return await catalogue.get_artist(uri)

    @staticmethod
    async def get_album(uri: str, /) -> AlbumDetails:
        """Fetch album metadata and track information."""
        async with Catalogue() as catalogue:
            return await catalogue.get_album(uri)

    @staticmethod
    async def get_track(uri: str, /) -> TrackDetails:
        """Fetch track metadata by Spotify URL, URI, or ID."""
        async with Catalogue() as catalogue:
            return await catalogue.get_track(uri)

    @staticmethod
    async def get_podcast(uri: str, /) -> PodcastDetails:
        """Read podcast metadata from a URL, URI, or bare show ID."""
        async with Catalogue() as catalogue:
            return await catalogue.get_podcast(uri)

    @staticmethod
    async def get_audiobook(uri: str, /) -> Audiobook:
        """Read audiobook metadata from its Spotify show link, URI or ID."""
        async with Catalogue() as catalogue:
            return await catalogue.get_audiobook(uri)

    @staticmethod
    async def get_podcast_episode(uri: str, /) -> PodcastEpisodeDetails:
        """Fetch a podcast episode by Spotify URL, URI, or ID."""
        async with Catalogue() as catalogue:
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
