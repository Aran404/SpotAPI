"""Explicit synchronous access for scripts that do not run an event loop."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncGenerator, Coroutine, Generator, Iterable, Sequence
from types import TracebackType
from typing import Any, Literal, Self, TypeVar

from .batch import BatchItem
from .cache import ResponseCache
from .catalogue import Catalogue, SpotifyItem
from .charts import Chart, list_charts
from .client import AsyncClient
from .embeds import Embed, get_embed
from .models import (
    Album,
    AlbumDetails,
    AlbumTrack,
    ArtistDetails,
    ArtistRelatedArtist,
    ArtistRelease,
    ArtistTopTrack,
    Audiobook,
    Canvas,
    Concert,
    CoverColors,
    PlaylistDetails,
    PlaylistEntry,
    PlaylistTrack,
    PodcastDetails,
    PodcastEpisodeDetails,
    PublicProfile,
    RecommendedTrack,
    SearchResults,
    SpotifyResource,
    TrackCredits,
    TrackDetails,
    Transcript,
)
from .models.catalogue import Playlist
from .models.catalogue.entities import AudiobookChapter
from .operations import DEFAULT_SEARCH_TYPES, ResourceInputKind, SearchInputKind, SearchOptions

T = TypeVar("T")


class SyncCatalogue:
    """Reuse SpotAPI's async implementation from a synchronous script.

    Use ``with SyncCatalogue() as spotify``. A single Runner owns all I/O and
    shutdown in the calling thread. Do not call this from an existing event
    loop; use Catalogue there. Optional cookie authentication is scoped to this
    client. Returned models behave exactly like async results, without I/O.
    """

    def __init__(
        self,
        *,
        proxy: str | None = None,
        language: str = "en",
        cache: ResponseCache | None = None,
        cookies: str | None = None,
    ) -> None:
        if cookies is not None and cache is not None:
            raise ValueError("Authenticated scopes cannot use response caching")
        self._catalogue = Catalogue(proxy=proxy, language=language, cache=cache)
        self._runner: asyncio.Runner | None = None
        self._client: AsyncClient | None = None
        self._thread = threading.get_ident()
        self._closed = False
        self._cookies = cookies
        self._proxy = proxy
        self._language = language

    def __enter__(self) -> Self:
        if self._closed or self._runner is not None:
            raise RuntimeError("SyncCatalogue is already open or closed")
        if threading.get_ident() != self._thread:
            raise RuntimeError("Use SyncCatalogue in its creating thread")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError("Use async Catalogue inside an event loop")
        self._runner = asyncio.Runner()
        try:
            if self._cookies is not None:
                self._client = self._run(
                    AsyncClient.from_cookies(
                        self._cookies, proxy=self._proxy, language=self._language
                    )
                )
                self._cookies = None
                self._catalogue = Catalogue(self._client)
            self._run(self._catalogue.__aenter__())
        except BaseException:
            self.close()
            raise
        return self

    def _run(self, operation: Coroutine[Any, Any, T]) -> T:
        if self._runner is None or threading.get_ident() != self._thread:
            operation.close()
            raise RuntimeError("Use with SyncCatalogue() in its creating thread")
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return self._runner.run(operation)
        operation.close()
        raise RuntimeError("Use async Catalogue inside an event loop")

    def close(self) -> None:
        """Close catalogue, authentication and the owned event loop exactly once."""
        if threading.get_ident() != self._thread:
            raise RuntimeError("Close SyncCatalogue in its creating thread")
        runner = self._runner
        if runner is not None:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                pass
            else:
                raise RuntimeError("Use async Catalogue inside an event loop")
        self._closed = True
        self._cookies = None
        if runner is None:
            return
        try:
            try:
                runner.run(self._catalogue.close())
            finally:
                if self._client is not None:
                    runner.run(self._client.close())
        finally:
            self._runner = None
            runner.close()

    def __exit__(
        self,
        typ: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    @staticmethod
    def list_charts() -> tuple[Chart, ...]:
        """List editorial shortcuts without opening a client."""
        return list_charts()

    def get(self, value: str, /, *, kind: ResourceInputKind | None = None) -> SpotifyItem:
        """Fetch a Spotify resource from its URL, URI, or typed ID."""
        return self._run(self._catalogue.get(value, kind=kind))

    def search(
        self,
        query: str,
        /,
        *,
        types: SearchInputKind | Iterable[SearchInputKind] = DEFAULT_SEARCH_TYPES,
        options: SearchOptions | None = None,
        limit: int | None = None,
    ) -> SearchResults:
        """Search selected categories in one request.

        Args:
            query: Nonempty search text; surrounding whitespace is stripped.
            types: One category or an iterable of categories. Defaults to
                tracks, artists, albums, playlists and podcasts. Singular,
                plural and documented aliases are accepted and deduplicated.
            options: Advanced Spotify inclusion options.
            limit: Results per category, from 1 to 100. Overrides the limit in
                ``options``; defaults to 20 when neither is supplied.

        Returns:
            Hits grouped by category. Unrequested or unavailable categories
            are empty tuples. Incomplete search previews may be skipped.

        Raises:
            ValueError: Query, categories or limit are invalid.
            RuntimeError: This catalogue is outside its open context.
            BaseClientError: Spotify returns an invalid search envelope.

        Example::

            results = self.search("Daft Punk", types=("track", "artist"))
            print(results.tracks[0].name)
        """
        return self._run(self._catalogue.search(query, types=types, options=options, limit=limit))

    def get_playlist(self, uri: str, /) -> PlaylistDetails:
        """Read public playlist metadata from a URL, URI, or ID."""
        return self._run(self._catalogue.get_playlist(uri))

    def get_related_artists(self, uri: str, /) -> tuple[ArtistRelatedArtist, ...]:
        """Explore the related artists shown on a public artist profile."""
        return self._run(self._catalogue.get_related_artists(uri))

    def get_radio(self, seed: str) -> SpotifyResource | None:
        """Resolve a track, artist or album into its Spotify radio playlist."""
        return self._run(self._catalogue.get_radio(seed))

    def get_playlist_recommendations(
        self, value: str, *, limit: int = 20, skip: Iterable[str] = ()
    ) -> tuple[RecommendedTrack, ...]:
        """Get suggested tracks without changing the playlist."""
        return self._run(
            self._catalogue.get_playlist_recommendations(value, limit=limit, skip=skip)
        )

    def get_canvases(self, tracks: Sequence[str]) -> tuple[Canvas, ...]:
        """Fetch available Canvas metadata in one protobuf request; no media is downloaded."""
        return self._run(self._catalogue.get_canvases(tracks))

    def get_canvas(self, track: str) -> Canvas | None:
        """Return an available Canvas record, or None when Spotify supplies none."""
        return self._run(self._catalogue.get_canvas(track))

    def get_track_credits(self, uri: str, /) -> TrackCredits:
        """Discover the performers, writers and producers credited on a song."""
        return self._run(self._catalogue.get_track_credits(uri))

    def get_artist_top_tracks(self, uri: str, /) -> tuple[ArtistTopTrack, ...]:
        """Read Spotify's public top-track selection and play counts for an artist."""
        return self._run(self._catalogue.get_artist_top_tracks(uri))

    def get_profile(self, value: str, /, *, limit: int = 20) -> PublicProfile:
        """Read a public user's profile and first public playlists; no login needed."""
        return self._run(self._catalogue.get_profile(value, limit=limit))

    def get_artist(self, uri: str, /) -> ArtistDetails:
        """Fetch an artist profile and overview by Spotify URL, URI, or ID."""
        return self._run(self._catalogue.get_artist(uri))

    def get_album(self, uri: str, /) -> AlbumDetails:
        """Fetch album metadata and track information."""
        return self._run(self._catalogue.get_album(uri))

    def get_track(self, uri: str, /) -> TrackDetails:
        """Fetch track metadata by Spotify URL, URI, or ID."""
        return self._run(self._catalogue.get_track(uri))

    def get_tracks(self, tracks: Sequence[str], /) -> tuple[TrackDetails, ...]:
        """Fetch track details in input order with up to eight concurrent reads."""
        return self._run(self._catalogue.get_tracks(tracks))

    def get_albums(self, albums: Sequence[str], /) -> tuple[AlbumDetails, ...]:
        """Fetch album details in input order with up to eight concurrent reads."""
        return self._run(self._catalogue.get_albums(albums))

    def get_artists(self, artists: Sequence[str], /) -> tuple[ArtistDetails, ...]:
        """Fetch artist details in input order with up to eight concurrent reads."""
        return self._run(self._catalogue.get_artists(artists))

    def get_podcast(self, uri: str, /) -> PodcastDetails:
        """Read podcast metadata from a URL, URI, or bare show ID."""
        return self._run(self._catalogue.get_podcast(uri))

    def get_audiobook(self, uri: str, /) -> Audiobook:
        """Read audiobook metadata from its Spotify show link, URI or ID."""
        return self._run(self._catalogue.get_audiobook(uri))

    def get_podcast_episode(self, uri: str, /) -> PodcastEpisodeDetails:
        """Fetch a podcast episode by Spotify URL, URI, or ID."""
        return self._run(self._catalogue.get_podcast_episode(uri))

    def get_chart(self, key: str) -> PlaylistDetails:
        """Read chart metadata; paginate its tracks using the returned playlist URI."""
        return self._run(self._catalogue.get_chart(key))

    def get_similar_albums(self, track: str, *, limit: int = 10) -> tuple[Album, ...]:
        """Read album recommendations seeded by a track ID, URI or URL.

        limit is from 1 to 50. An empty list is valid; a missing collection is
        a contract error. Recommendations can vary by request region.
        """
        return self._run(self._catalogue.get_similar_albums(track, limit=limit))

    def get_artist_events(self, artist: str) -> tuple[Concert, ...]:
        """Read upcoming artist concerts; returned inventory depends on region."""
        return self._run(self._catalogue.get_artist_events(artist))

    def get_artist_discovered_on(self, artist: str, /) -> tuple[Playlist | None, ...]:
        """Read the bounded discovery selection; unavailable slots remain None."""
        return self._run(self._catalogue.get_artist_discovered_on(artist))

    def get_colors(self, image: str) -> CoverColors:
        """Extract a palette from a Spotify image URI or CDN image URL.

        No image bytes are downloaded. Supply artwork identity rather than a
        track ID; existing cover-art models expose the corresponding image URLs.
        """
        return self._run(self._catalogue.get_colors(image))

    def get_transcript(self, episode: str) -> Transcript:
        """Read episode captions; supply cookies when constructing SyncCatalogue."""
        return self._run(self._catalogue.get_transcript(episode))

    def fetch_many(
        self, values: Sequence[str], *, kind: ResourceInputKind | None = None, concurrency: int = 8
    ) -> tuple[BatchItem[SpotifyItem], ...]:
        """Read resources with per-input errors; kind allows same-type bare IDs."""
        return self._run(self._catalogue.fetch_many(values, kind=kind, concurrency=concurrency))

    def get_embed(
        self, value: str, *, kind: ResourceInputKind | None = None, browser: bool = False
    ) -> Embed:
        """Read public embed metadata in the owned event loop."""
        return self._run(get_embed(value, kind=kind, browser=browser))

    def lookup(
        self, value: str, *, kind: ResourceInputKind | None = None, fallback: bool = True
    ) -> SpotifyItem | Embed:
        """Read catalogue details with an explicitly typed anonymous fallback."""
        return self._run(self._catalogue.lookup(value, kind=kind, fallback=fallback))

    def _iterate(self, stream: AsyncGenerator[T, None]) -> Generator[T, None, None]:
        try:
            while True:
                try:
                    yield self._run(anext(stream))
                except StopAsyncIteration:
                    return
        finally:
            if self._runner is not None and threading.get_ident() == self._thread:
                self._run(stream.aclose())

    def get_playlist_items(
        self, value: str, *, limit: int = 100
    ) -> Generator[Sequence[PlaylistEntry], None, None]:
        """Iterate occurrence pages within the open synchronous scope."""
        return self._iterate(self._catalogue.get_playlist_items(value, limit=limit))

    def get_playlist_tracks(
        self, value: str, *, limit: int = 100
    ) -> Generator[Sequence[PlaylistTrack], None, None]:
        """Iterate available music-track pages without collecting the whole playlist."""
        return self._iterate(self._catalogue.get_playlist_tracks(value, limit=limit))

    def get_album_tracks(
        self, value: str, *, limit: int = 50
    ) -> Generator[Sequence[AlbumTrack], None, None]:
        """Iterate all album-track pages in disc and track order."""
        return self._iterate(self._catalogue.get_album_tracks(value, limit=limit))

    def get_artist_releases(
        self,
        value: str,
        *,
        kind: Literal["all", "albums", "singles", "compilations"] = "all",
        limit: int = 50,
    ) -> Generator[Sequence[ArtistRelease], None, None]:
        """Iterate discography pages without materializing the full release history."""
        return self._iterate(self._catalogue.get_artist_releases(value, kind=kind, limit=limit))

    def get_podcast_episodes(
        self, value: str, *, limit: int = 50
    ) -> Generator[Sequence[PodcastEpisodeDetails], None, None]:
        """Iterate episode pages within the open synchronous scope."""
        return self._iterate(self._catalogue.get_podcast_episodes(value, limit=limit))

    def get_audiobook_chapters(
        self, value: str, *, limit: int = 50
    ) -> Generator[Sequence[AudiobookChapter], None, None]:
        """Iterate chapter pages, subject to the request region and account entitlement."""
        return self._iterate(self._catalogue.get_audiobook_chapters(value, limit=limit))
