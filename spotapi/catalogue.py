"""Reusable, context-managed access to Spotify’s public catalogue."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Awaitable, Callable, Iterable, Mapping, Sequence
from contextlib import aclosing
from dataclasses import asdict, dataclass, replace
from functools import partial
from typing import (
    Any,
    Literal,
    Self,
    TypeAlias,
    TypeVar,
    cast,
    overload,
)
from urllib.parse import quote, unquote, urlsplit

from .client import AsyncClient
from .datastruct import ObjectDict
from .discovery import Canvas, RecommendedTrack, recommended_tracks
from .operations import (
    DEFAULT_SEARCH_TYPES,
    SEARCH_DESKTOP_SECTIONS,
    SEARCH_OPERATION_SECTIONS,
    SEARCH_RESULT_FIELDS,
    InclusionParameters,
    Operations,
    ResourceInputKind,
    ResourceKind,
    SearchInputKind,
    SearchKind,
    normalize_resource_kind,
    normalize_search_kind,
)
from .playback import records
from .protobuf import ProtoMessage, encode_field
from .queries import Queries
from .query import QueryClient, SharedQueryClient
from .session import AuthSession, normalize_language
from .specialized.data_wrappers import (
    Album,
    AlbumDetails,
    Artist,
    ArtistDetails,
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
    Track,
    TrackDetails,
    User,
    from_dict,
)
from .specialized.data_wrappers.album_details import AlbumTrack
from .specialized.data_wrappers.artist_details import (
    ArtistRelatedArtist,
    ArtistRelatedArtists,
    ArtistRelease,
    ArtistReleaseGroups,
    ArtistTopTrack,
)
from .specialized.data_wrappers.catalogue import AudiobookChapter
from .specialized.data_wrappers.credits import Credit, TrackCredits
from .types import BaseClientError

__all__ = (
    "Audiobook",
    "Author",
    "Episode",
    "Genre",
    "User",
    "PublicProfile",
    "PlaylistDetails",
    "PlaylistEntry",
    "PlaylistTrack",
    "PodcastDetails",
    "Album",
    "AlbumDetails",
    "Artist",
    "ArtistDetails",
    "InclusionParameters",
    "Operations",
    "Playlist",
    "Podcast",
    "PodcastEpisodeDetails",
    "Catalogue",
    "Queries",
    "ResourceInputKind",
    "ResourceKind",
    "SearchInputKind",
    "SearchKind",
    "SearchResults",
    "SpotifyItem",
    "SpotifyResource",
    "Track",
    "TrackDetails",
)

_ResultT = TypeVar("_ResultT")
_ShowItemT = TypeVar("_ShowItemT", PodcastEpisodeDetails, AudiobookChapter)


async def _get_many(
    values: Sequence[str],
    kind: ResourceInputKind,
    get_one: Callable[[str], Awaitable[_ResultT]],
) -> tuple[_ResultT, ...]:
    """Resolve inputs before issuing bounded, ordered reads on one client."""
    if isinstance(values, str):
        raise TypeError("Pass a collection of Spotify resources")

    uris = [parse_spotify_resource(value, kind).uri for value in values]
    results: list[_ResultT] = []

    for offset in range(0, len(uris), 8):
        batch = await asyncio.gather(
            *(get_one(uri) for uri in uris[offset : offset + 8]),
            return_exceptions=True,
        )

        for item in batch:
            if isinstance(item, BaseException):
                raise item

            results.append(item)

    return tuple(results)


SpotifyItem: TypeAlias = (
    TrackDetails
    | AlbumDetails
    | ArtistDetails
    | PodcastEpisodeDetails
    | PlaylistDetails
    | PodcastDetails
    | PublicProfile
    | Audiobook
    | ObjectDict
)
SearchEntity: TypeAlias = (
    Track | Album | Artist | Playlist | Podcast | Audiobook | Episode | User | Author | Genre
)


@dataclass(slots=True, frozen=True)
class SpotifyResource:
    """A normalized Spotify resource parsed from a URL, URI, or typed ID."""

    kind: ResourceKind
    id: str
    uri: str
    url: str


@dataclass(slots=True, frozen=True)
class SearchResults:
    """Typed search hits grouped by category."""

    query: str
    requested_types: tuple[SearchKind, ...]
    tracks: tuple[Track, ...] = ()
    albums: tuple[Album, ...] = ()
    artists: tuple[Artist, ...] = ()
    playlists: tuple[Playlist, ...] = ()
    podcasts: tuple[Podcast, ...] = ()
    audiobooks: tuple[Audiobook, ...] = ()
    episodes: tuple[Episode, ...] = ()
    authors: tuple[Author, ...] = ()
    genres: tuple[Genre, ...] = ()
    users: tuple[User, ...] = ()

    def __getitem__(self, kind: str) -> tuple[SearchEntity, ...]:
        """Return results by singular, plural, or legacy entity name."""
        normalized = normalize_search_kind(kind)
        field_name = SEARCH_RESULT_FIELDS[normalized]

        return cast(tuple[SearchEntity, ...], getattr(self, field_name))

    def __bool__(self) -> bool:
        """Return whether at least one category contains a result."""
        return any(
            (
                self.tracks,
                self.albums,
                self.artists,
                self.playlists,
                self.podcasts,
                self.audiobooks,
                self.episodes,
                self.authors,
                self.genres,
                self.users,
            )
        )

    def __len__(self) -> int:
        """Return the total number of hits across all requested categories."""
        return sum(
            len(items)
            for items in (
                self.tracks,
                self.albums,
                self.artists,
                self.playlists,
                self.podcasts,
                self.audiobooks,
                self.episodes,
                self.authors,
                self.genres,
                self.users,
            )
        )


def _validate_page_limit(limit: int) -> None:
    """Reject unbounded or invalid catalogue pagination limits."""
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("limit must be an integer between 1 and 100")


async def _show_details(value: str, queries: Queries) -> PodcastDetails | Audiobook:
    """Resolve a show into a podcast or audiobook using its native type."""
    resource = parse_spotify_resource(
        value, "show" if ":" not in value and "/" not in value else None
    )

    if resource.kind not in {"show", "audiobook"}:
        raise ValueError("Expected a Spotify show or audiobook")

    uri = f"spotify:show:{resource.id}" if resource.kind == "audiobook" else resource.uri

    response = await queries.query(Operations.QUERY_SHOW_METADATA_V2.value, {"uri": uri})

    data = Queries.resource_data(response, Operations.QUERY_SHOW_METADATA_V2, expected_uri=uri)

    try:
        if data.get("__typename") == "Audiobook":
            return from_dict(Audiobook, data)

        if data.get("__typename") == "Podcast":
            return from_dict(PodcastDetails, data)
    except (TypeError, ValueError) as exc:
        raise BaseClientError(f"Invalid show metadata: {exc}") from exc

    raise BaseClientError("Spotify returned no podcast or audiobook metadata")


def _page(data: ObjectDict, *path: str) -> ObjectDict:
    """Extract a nested page or reject a changed response contract."""
    current: object = data

    for key in path:
        current = current.get(key) if isinstance(current, ObjectDict) else None

    if not isinstance(current, ObjectDict):
        raise BaseClientError(f"Spotify response has no {'.'.join(path)} collection")

    return current


def _playlist_entry(value: object) -> PlaylistEntry:
    """Parse an occurrence while retaining unavailable entries and UIDs."""
    if not isinstance(value, ObjectDict):
        raise BaseClientError("Playlist response contains an invalid occurrence")

    wrapper: object = value.get("itemV2")
    payload: object = wrapper.get("data") if isinstance(wrapper, ObjectDict) else None
    item: PlaylistTrack | Episode | None = None

    if isinstance(payload, ObjectDict):
        uri: object = payload.get("uri")

        if isinstance(uri, str):
            if uri.startswith("spotify:track:"):
                item = from_dict(PlaylistTrack, payload)
            elif uri.startswith("spotify:episode:"):
                item = from_dict(Episode, payload)

    uid: object = value.get("uid")
    added: object = value.get("addedAt")
    timestamp: object = added.get("isoString") if isinstance(added, ObjectDict) else None

    return PlaylistEntry(
        item,
        uid if isinstance(uid, str) else None,
        timestamp if isinstance(timestamp, str) else None,
    )


def parse_spotify_resource(
    value: str,
    kind: ResourceInputKind | None = None,
) -> SpotifyResource:
    """Parse and validate a Spotify URL, URI, or ID."""
    value = value.strip()

    if not value:
        raise ValueError("Spotify resource must not be empty")

    parsed_kind: str
    resource_id: str

    if value.startswith("spotify:"):
        parts = value.split(":")

        if len(parts) == 3:
            _, parsed_kind, resource_id = parts
        elif len(parts) == 5 and parts[1] == "user" and parts[3] == "playlist":
            # Legacy user playlist URI: spotify:user:<user>:playlist:<id>.
            parsed_kind, resource_id = "playlist", parts[4]
        else:
            raise ValueError(f"Unsupported Spotify URI: {value!r}")
    else:
        try:
            parsed = urlsplit(value)
        except ValueError as exc:
            raise ValueError(f"Invalid Spotify URL: {value!r}") from exc

        if parsed.scheme in {"http", "https"}:
            hostname = (parsed.hostname or "").casefold()

            if hostname not in {"open.spotify.com", "www.open.spotify.com"}:
                if hostname in {"spotify.link", "www.spotify.link", "spoti.fi"}:
                    raise ValueError("Expand Spotify short links to an open.spotify.com URL")

                raise ValueError("Expected a URL on open.spotify.com")

            segments = [unquote(part) for part in parsed.path.split("/") if part]

            if segments and segments[0].startswith("intl-"):
                segments.pop(0)

            if segments and segments[0] in {"embed", "embed-podcast"}:
                segments.pop(0)

            # Legacy profile playlist path: /user/<username>/playlist/<id>.
            if len(segments) >= 4 and segments[0] == "user" and segments[2] == "playlist":
                parsed_kind, resource_id = "playlist", segments[3]
            elif len(segments) >= 2:
                parsed_kind, resource_id = segments[0], segments[1]
            else:
                raise ValueError(f"URL does not identify a Spotify resource: {value!r}")
        elif parsed.scheme or "://" in value:
            raise ValueError("Expected a Spotify URI or URL on open.spotify.com")
        else:
            if kind is None:
                raise ValueError(
                    "A bare Spotify ID is ambiguous; pass kind='track', 'album', etc."
                )

            parsed_kind, resource_id = kind, value

    canonical_kind = normalize_resource_kind(parsed_kind)

    if kind is not None and normalize_resource_kind(kind) != canonical_kind:
        raise ValueError(f"Resource is a {canonical_kind}, but kind={kind!r} was requested")

    if (
        not resource_id
        or len(resource_id) > 128
        or any(character.isspace() or character in "/?:#" for character in resource_id)
    ):
        raise ValueError(f"Invalid Spotify resource ID: {resource_id!r}")

    normalized_uri = f"spotify:{canonical_kind}:{resource_id}"
    normalized_url = f"https://open.spotify.com/{canonical_kind}/{quote(resource_id, safe='')}"

    return SpotifyResource(
        kind=canonical_kind,
        id=resource_id,
        uri=normalized_uri,
        url=normalized_url,
    )


def _search_section(data: ObjectDict, names: tuple[str, ...]) -> ObjectDict:
    """Select a named result collection from a consolidated search response."""
    root: object = data.get("searchV2", data.get("search"))

    if not isinstance(root, ObjectDict):
        raise BaseClientError("searchDesktop: missing searchV2 response")

    for name in names:
        section: object = root.get(name)

        if isinstance(section, ObjectDict):
            return section

    raise BaseClientError(f"searchDesktop: response contains no {'/'.join(names)} section")


def _parse_show_page(
    page: ObjectDict, operation: Operations, model: type[_ShowItemT]
) -> list[_ShowItemT]:
    """Deserialize podcast episode or audiobook chapter occurrences."""
    items: object = page["items"] if "items" in page else page.get("_items")

    if not isinstance(items, list):
        raise BaseClientError(f"{operation.value}: missing items")

    results: list[_ShowItemT] = []

    for entry in cast(list[object], items):
        if not isinstance(entry, Mapping):
            raise BaseClientError(f"{operation.value}: invalid entry")

        entry_data = cast(Mapping[str, object], entry)
        entity: object = entry_data.get("entity")

        if not isinstance(entity, Mapping):
            raise BaseClientError(f"{operation.value}: missing entity")

        entity_data = cast(Mapping[str, object], entity)
        payload: object = entity_data.get("data")

        if payload is None:
            continue

        if not isinstance(payload, Mapping):
            raise BaseClientError(f"{operation.value}: invalid entity data")

        try:
            item = from_dict(model, cast(Mapping[str, Any], payload))
        except (LookupError, TypeError, ValueError, AttributeError) as exc:
            raise BaseClientError(f"{operation.value}: failed to parse entity: {exc}") from exc

        if not item.id or not item.name or not item.uri:
            raise BaseClientError(f"{operation.value}: incomplete entity data")

        results.append(item)

    return results


async def _show_pages(
    variables: dict[str, Any],
    queries: Queries,
    operation: Operations,
    connection: str,
    model: type[_ShowItemT],
) -> AsyncGenerator[Sequence[_ShowItemT], None]:
    """Yield typed pages from a show's episode or chapter connection."""
    async for page in queries.paginate(
        operation.value,
        variables,
        extract_page=lambda response: _page(response, "podcastUnionV2", connection),
    ):
        yield _parse_show_page(page, operation, model)


class Catalogue:
    """Search the catalogue; supply a client to include its private resources."""

    __slots__ = ("_queries", "_owner", "_proxy", "_session", "_language", "_entered", "_closed")

    def __init__(
        self,
        client: AsyncClient | AuthSession | None = None,
        *,
        proxy: str | None = None,
        queries: Queries | None = None,
        language: str | None = None,
    ) -> None:
        """Configure an owned anonymous catalogue or borrow a supplied client or query owner."""
        if (client is not None and queries is not None) or (
            proxy is not None and (queries is not None or client is not None)
        ):
            raise ValueError("Configure one client, query owner or proxy")

        self._queries = queries
        self._owner: SharedQueryClient | None = None
        self._proxy = proxy
        if language is not None and (client is not None or queries is not None):
            raise ValueError("Configure the language on the supplied client or session")
        self._language = normalize_language(language) if language is not None else None
        self._session = client.session if isinstance(client, AsyncClient) else client
        self._entered = False
        self._closed = False

    async def __aenter__(self) -> Self:
        """Enter this resource's asynchronous ownership scope."""
        if self._closed or self._entered:
            raise RuntimeError("Catalogue is already open or closed")

        if self._queries is None:
            session = self._session

            async def borrow() -> QueryClient:
                """Wrap the supplied session without taking ownership of its authentication."""
                assert session is not None
                return QueryClient(session)

            factory: Callable[[], Awaitable[QueryClient]] | None = None
            if session is not None:
                factory = borrow
            elif self._proxy:
                factory = partial(
                    QueryClient.create, proxy=self._proxy, language=self._language or "en"
                )
            elif self._language is not None:
                factory = partial(QueryClient.create, language=self._language)
            self._owner = SharedQueryClient(factory)
            self._queries = Queries(self._owner)

        self._entered = True

        return self

    async def __aexit__(self, _typ: object, error: BaseException | None, _tb: object) -> None:
        """Release resources owned by this asynchronous scope."""
        try:
            await self.close()
        except Exception as exc:
            if isinstance(error, asyncio.CancelledError):
                raise error from exc

            raise

    async def close(self) -> None:
        """Drain catalogue queries and release only the session this catalogue owns."""
        self._entered = False
        self._closed = True

        if self._owner is not None:
            await self._owner.close()

    @property
    def queries(self) -> Queries:
        """Return the active lower-level query interface; require an open catalogue scope."""
        if not self._entered or self._queries is None:
            raise RuntimeError("Catalogue is not open; use async with Catalogue()")

        return self._queries

    def parse_url(
        self,
        value: str,
        /,
        *,
        kind: ResourceInputKind | None = None,
    ) -> SpotifyResource:
        """Normalize a Spotify URL, URI, or typed ID."""
        return parse_spotify_resource(value, kind)

    async def get(
        self,
        value: str,
        /,
        *,
        kind: ResourceInputKind | None = None,
    ) -> SpotifyItem:
        """Fetch a Spotify resource from its URL, URI, or typed ID."""
        resource = parse_spotify_resource(value, kind)

        match resource.kind:
            case "track":
                return await self.get_track(resource.uri)
            case "album":
                return await self.get_album(resource.uri)
            case "artist":
                return await self.get_artist(resource.uri)
            case "episode":
                return await self.get_podcast_episode(resource.uri)
            case "playlist":
                return await self.get_playlist(resource.uri)
            case "show":
                return await _show_details(resource.uri, self.queries)
            case "user":
                return await self.get_profile(resource.uri)
            case "audiobook":
                return await self.get_audiobook(resource.uri)
            case "chapter":
                return await self.get_resource(resource.uri, Operations.GET_EPISODE_OR_CHAPTER)

    @overload
    async def get_resource(
        self,
        uri: str,
        operation: Operations,
        /,
    ) -> ObjectDict: ...
    @overload
    async def get_resource(
        self,
        uri: str,
        operation: Operations,
        typ: type[_ResultT],
        /,
    ) -> _ResultT: ...
    async def get_resource(
        self,
        uri: str,
        operation: Operations,
        typ: type[_ResultT] | None = None,
        /,
    ) -> ObjectDict | _ResultT:
        """Execute a specific resource operation."""
        resource = parse_spotify_resource(uri)
        wrapper = self.queries

        if typ is None:
            return await wrapper.resource(resource.uri, operation)

        return await wrapper.resource(resource.uri, operation, typ)

    async def search(
        self,
        query: str,
        /,
        *,
        types: SearchInputKind | Iterable[SearchInputKind] = DEFAULT_SEARCH_TYPES,
        parameters: InclusionParameters | None = None,
        limit: int | None = None,
    ) -> SearchResults:
        """Search selected categories in one request.

        Example::

            results = await self.search("Daft Punk", types=("track", "artist"))
            print(results.tracks[0].name)
        """
        search_term = query.strip()

        if not search_term:
            raise ValueError("Search query must not be empty")

        requested_values: Iterable[SearchInputKind]
        requested_values = (types,) if isinstance(types, str) else types
        selected: list[SearchKind] = []

        for value in requested_values:
            normalized = normalize_search_kind(value)

            if normalized not in selected:
                selected.append(normalized)

        if not selected:
            raise ValueError("At least one search type must be requested")

        if parameters is None:
            options = InclusionParameters(limit=20 if limit is None else limit)
        elif limit is None:
            options = parameters
        else:
            options = replace(parameters, limit=limit)

        if type(options.limit) is not int or not 1 <= options.limit <= 100:
            raise ValueError("Search limit must be between 1 and 100")

        options = replace(
            options,
            includeAudiobooks=(options.includeAudiobooks or "audiobook" in selected),
            includeAuthors=(options.includeAuthors or "author" in selected),
            includeEpisodeContentRatingsV2=(
                options.includeEpisodeContentRatingsV2 or "episode" in selected
            ),
        )

        return await self._search_desktop(self.queries, search_term, selected, options)

    async def _search_desktop(
        self,
        wrapper: Queries,
        query: str,
        kinds: Sequence[SearchKind],
        parameters: InclusionParameters,
    ) -> SearchResults:
        """Fetch selected search categories together using one native search request."""
        variables: dict[str, Any] = {
            "searchTerm": query,
            "offset": 0,
            **asdict(parameters),
            "isPrefix": None,
            "sectionFilters": ["GENERIC"],
        }

        response = await wrapper.query(Operations.SEARCH_DESKTOP.value, variables)

        root: object = response.get("searchV2", response.get("search"))

        if not isinstance(root, ObjectDict):
            raise BaseClientError("searchDesktop: missing searchV2 response")

        def parse(typ: type[_ResultT], kind: SearchKind) -> tuple[_ResultT, ...]:
            """Decode the expected typed item from a raw search record."""
            if kind not in kinds:
                return ()

            section = next(
                (
                    candidate
                    for name in SEARCH_DESKTOP_SECTIONS[kind]
                    if isinstance(candidate := root.get(name), ObjectDict)
                ),
                None,
            )

            if section is None:
                return ()

            return tuple(
                wrapper.parse_items(section, typ, Operations.SEARCH_DESKTOP, skip_invalid=True)
            )

        return SearchResults(
            query=query,
            requested_types=tuple(kinds),
            tracks=parse(Track, "track"),
            albums=parse(Album, "album"),
            artists=parse(Artist, "artist"),
            playlists=parse(Playlist, "playlist"),
            podcasts=parse(Podcast, "podcast"),
            audiobooks=parse(Audiobook, "audiobook"),
            episodes=parse(Episode, "episode"),
            users=parse(User, "user"),
            authors=parse(Author, "author"),
            genres=parse(Genre, "genre"),
        )

    def search_typed(
        self,
        typ: type[_ResultT],
        operation: Operations,
        query: str,
        /,
        *,
        parameters: InclusionParameters | None = None,
    ) -> AsyncGenerator[Sequence[_ResultT], None]:
        """Stream typed result pages for a single persisted search operation."""
        query = query.strip()

        if not query:
            raise ValueError("Search query must not be empty")

        options = parameters if parameters is not None else InclusionParameters()

        _validate_page_limit(options.limit)

        options = replace(
            options,
            includeAudiobooks=options.includeAudiobooks
            or operation == Operations.SEARCH_AUDIOBOOKS,
            includeAuthors=options.includeAuthors or operation == Operations.SEARCH_AUTHORS,
            includeEpisodeContentRatingsV2=options.includeEpisodeContentRatingsV2
            or operation == Operations.SEARCH_EPISODES,
        )
        wrapper = self.queries
        section_names = SEARCH_OPERATION_SECTIONS.get(operation)

        if section_names is None:
            return wrapper.typed_search(typ, operation, query, parameters=options)

        return wrapper.typed_search(
            typ,
            Operations.SEARCH_DESKTOP,
            query,
            parameters=options,
            extract_page=lambda data: _search_section(data, section_names),
            skip_invalid=True,
        )

    def search_tracks(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Track], None]:
        """Stream typed pages of matching tracks."""
        _validate_page_limit(limit)

        return self.search_typed(
            Track,
            Operations.SEARCH_TRACKS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_albums(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Album], None]:
        """Stream typed pages of matching albums."""
        _validate_page_limit(limit)

        return self.search_typed(
            Album,
            Operations.SEARCH_ALBUMS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_artists(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Artist], None]:
        """Stream typed pages of matching artists."""
        _validate_page_limit(limit)

        return self.search_typed(
            Artist,
            Operations.SEARCH_ARTISTS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_playlists(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Playlist], None]:
        """Stream typed pages of matching playlists."""
        _validate_page_limit(limit)

        return self.search_typed(
            Playlist,
            Operations.SEARCH_PLAYLISTS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_podcasts(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Podcast], None]:
        """Stream typed pages of matching podcasts."""
        _validate_page_limit(limit)

        return self.search_typed(
            Podcast,
            Operations.SEARCH_PODCASTS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_episodes(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Episode], None]:
        """Stream typed pages of matching episodes."""
        _validate_page_limit(limit)

        return self.search_typed(
            Episode,
            Operations.SEARCH_EPISODES,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_audiobooks(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Audiobook], None]:
        """Stream typed pages of matching audiobooks."""
        _validate_page_limit(limit)

        return self.search_typed(
            Audiobook,
            Operations.SEARCH_AUDIOBOOKS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_users(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[User], None]:
        """Stream typed pages of matching users."""
        _validate_page_limit(limit)

        return self.search_typed(
            User,
            Operations.SEARCH_USERS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_authors(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Author], None]:
        """Stream typed pages of matching authors."""
        _validate_page_limit(limit)

        return self.search_typed(
            Author,
            Operations.SEARCH_AUTHORS,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    def search_genres(
        self, query: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[Genre], None]:
        """Stream typed pages of matching genres."""
        _validate_page_limit(limit)

        return self.search_typed(
            Genre,
            Operations.SEARCH_GENRES,
            query,
            parameters=InclusionParameters(limit=limit),
        )

    async def iter_tracks(self, query: str, /) -> AsyncGenerator[Track, None]:
        """Yield tracks individually, hiding search-page boundaries."""
        async for page in self.search_tracks(query):
            for track in page:
                yield track

    async def iter_albums(self, query: str, /) -> AsyncGenerator[Album, None]:
        """Yield albums individually, hiding search-page boundaries."""
        async for page in self.search_albums(query):
            for album in page:
                yield album

    async def iter_artists(self, query: str, /) -> AsyncGenerator[Artist, None]:
        """Yield artists individually, hiding search-page boundaries."""
        async for page in self.search_artists(query):
            for artist in page:
                yield artist

    async def iter_playlists(self, query: str, /) -> AsyncGenerator[Playlist, None]:
        """Yield playlists individually, hiding search-page boundaries."""
        async for page in self.search_playlists(query):
            for playlist in page:
                yield playlist

    async def iter_podcasts(self, query: str, /) -> AsyncGenerator[Podcast, None]:
        """Yield podcast shows individually, hiding search-page boundaries."""
        async for page in self.search_podcasts(query):
            for podcast in page:
                yield podcast

    async def get_playlist(self, uri: str, /) -> PlaylistDetails:
        """Read public playlist metadata from a URL, URI, or ID."""
        resource = parse_spotify_resource(uri, "playlist")

        return await self.get_resource(
            resource.uri, Operations.FETCH_PLAYLIST_METADATA, PlaylistDetails
        )

    async def get_playlist_items(
        self, uri: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[PlaylistEntry], None]:
        """Page through tracks, episodes and unavailable occurrences in source order."""
        _validate_page_limit(limit)

        resource = parse_spotify_resource(uri, "playlist")

        async for page in self.queries.paginate(
            Operations.FETCH_PLAYLIST_CONTENTS.value,
            {
                "uri": resource.uri,
                "offset": 0,
                "limit": limit,
                "enableWatchFeedEntrypoint": False,
                "includeEpisodeContentRatingsV2": True,
            },
            extract_page=lambda data: _page(data, "playlistV2", "content"),
        ):
            items: object = page.get("items")

            if not isinstance(items, list):
                raise BaseClientError("Playlist response has no items list")

            yield [_playlist_entry(item) for item in cast(list[object], items)]

    async def iter_playlist_items(
        self, uri: str, /, *, limit: int = 100
    ) -> AsyncGenerator[PlaylistEntry, None]:
        """Yield playlist occurrences individually, preserving duplicate songs."""
        async with aclosing(self.get_playlist_items(uri, limit=limit)) as pages:
            async for page in pages:
                for item in page:
                    yield item

    async def get_playlist_tracks(
        self, uri: str, /, *, limit: int = 100
    ) -> AsyncGenerator[Sequence[PlaylistTrack], None]:
        """Page through available music tracks, including optional BPM and musical keys."""
        async with aclosing(self.get_playlist_items(uri, limit=limit)) as pages:
            async for page in pages:
                yield [entry.item for entry in page if isinstance(entry.item, PlaylistTrack)]

    async def get_album_tracks(
        self, uri: str, /, *, limit: int = 50
    ) -> AsyncGenerator[Sequence[AlbumTrack], None]:
        """Read every album track in disc/track order, including albums over one page."""
        _validate_page_limit(limit)

        resource = parse_spotify_resource(uri, "album")

        async for page in self.queries.paginate(
            Operations.QUERY_ALBUM_TRACKS.value,
            {"uri": resource.uri, "offset": 0, "limit": limit},
            extract_page=lambda data: _page(data, "albumUnion", "tracksV2"),
        ):
            items: object = page.get("items")

            if not isinstance(items, list):
                raise BaseClientError("Album response has no items list")

            tracks: list[AlbumTrack] = []

            for item in cast(list[object], items):
                if not isinstance(item, ObjectDict):
                    raise BaseClientError("Album response contains an invalid item")

                payload: object = item.get("track")

                if payload is not None:
                    tracks.append(from_dict(AlbumTrack, payload))

            yield tracks

    async def get_related_artists(self, uri: str, /) -> tuple[ArtistRelatedArtist, ...]:
        """Explore the related artists shown on a public artist profile."""
        resource = parse_spotify_resource(uri, "artist")

        data = await self.queries.query(
            Operations.QUERY_ARTIST_RELATED.value, {"uri": resource.uri}
        )

        artist: object = data.get("artistUnion")
        related: object = artist.get("relatedContent") if isinstance(artist, ObjectDict) else None
        collection: object = (
            related.get("relatedArtists") if isinstance(related, ObjectDict) else None
        )

        if collection is None:
            raise BaseClientError("Artist response has no related artists collection")

        return tuple(from_dict(ArtistRelatedArtists, collection).items)

    async def get_artist_releases(
        self,
        uri: str,
        /,
        *,
        kind: Literal["all", "albums", "singles", "compilations"] = "all",
        limit: int = 50,
    ) -> AsyncGenerator[Sequence[ArtistRelease], None]:
        """Page through an artist's releases, newest first, flattening release groups."""
        _validate_page_limit(limit)

        operations = {
            "all": Operations.QUERY_ARTIST_DISCOGRAPHY_ALL,
            "albums": Operations.QUERY_ARTIST_DISCOGRAPHY_ALBUMS,
            "singles": Operations.QUERY_ARTIST_DISCOGRAPHY_SINGLES,
            "compilations": Operations.QUERY_ARTIST_DISCOGRAPHY_COMPILATIONS,
        }

        if kind not in operations:
            raise ValueError("kind must be all, albums, singles, or compilations")

        resource = parse_spotify_resource(uri, "artist")

        async for page in self.queries.paginate(
            operations[kind].value,
            {"uri": resource.uri, "offset": 0, "limit": limit, "order": "DATE_DESC"},
            extract_page=lambda data: _page(data, "artistUnion", "discography", kind),
        ):
            groups = from_dict(ArtistReleaseGroups, page)
            yield [release for group in groups.items for release in group.releases.items]

    async def get_radio(self, seed: str) -> SpotifyResource | None:
        """Resolve a track, artist or album into its Spotify radio playlist."""
        resource = parse_spotify_resource(
            seed, "track" if ":" not in seed and "/" not in seed else None
        )
        if resource.kind not in {"track", "artist", "album"}:
            raise ValueError("Radio needs a track, artist or album")
        response = await self.queries.get_json(
            "https://spclient.wg.spotify.com/inspiredby-mix/v2/seed_to_playlist/"
            + quote(resource.uri, safe=":"),
            query={"response-format": "json"},
        )
        if not isinstance(response.get("mediaItems"), list):
            raise BaseClientError("Spotify returned no radio result")
        for item in records(response["mediaItems"]):
            uri = item.get("uri")
            if isinstance(uri, str) and uri.startswith("spotify:playlist:"):
                return parse_spotify_resource(uri, "playlist")
        return None

    async def get_playlist_recommendations(
        self, value: str, *, limit: int = 20, skip: Iterable[str] = ()
    ) -> tuple[RecommendedTrack, ...]:
        """Get suggested tracks without changing the playlist."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")
        if isinstance(skip, str):
            raise TypeError("skip must be a collection of tracks")
        resource = parse_spotify_resource(value, "playlist")
        response = await self.queries.request(
            "POST",
            "https://spclient.wg.spotify.com/playlistextender/extendp/",
            json={
                "playlistURI": resource.uri,
                "trackSkipIDs": [parse_spotify_resource(track, "track").id for track in skip],
                "numResults": limit,
            },
        )
        if response.json is None:
            raise BaseClientError("Spotify returned no recommendation response")
        return recommended_tracks(response.json)

    async def get_canvases(self, tracks: Sequence[str]) -> tuple[Canvas, ...]:
        """Fetch available Canvas metadata in one protobuf request; no media is downloaded."""
        if isinstance(tracks, str):
            raise TypeError("Pass a collection of tracks")
        if len(tracks) > 50:
            raise ValueError("Request at most 50 canvases at once")
        if not tracks:
            return ()
        uris = [parse_spotify_resource(track, "track").uri for track in tracks]
        body = b"".join(encode_field(1, encode_field(1, uri)) for uri in uris)
        response = await self.queries.request(
            "POST",
            "https://spclient.wg.spotify.com/canvaz-cache/v0/canvases",
            headers={"accept": "application/protobuf", "content-type": "application/x-protobuf"},
            body=body,
        )
        if "protobuf" not in response.headers.get("content-type", ""):
            raise BaseClientError("Spotify returned no protobuf Canvas response")
        return tuple(
            Canvas.from_message(item) for item in ProtoMessage.decode(response.body).messages(1)
        )

    async def get_canvas(self, track: str) -> Canvas | None:
        """Return an available Canvas record, or None when Spotify supplies none."""
        canvases = await self.get_canvases((track,))
        return canvases[0] if canvases else None

    async def get_track_credits(self, uri: str, /) -> TrackCredits:
        """Discover the performers, writers and producers credited on a song."""
        resource = parse_spotify_resource(uri, "track")

        data = await self.queries.query(
            Operations.QUERY_TRACK_CREDITS_GROUPED_MODAL.value,
            {"trackUri": resource.uri},
        )

        track: object = data.get("trackUnion")
        trait: object = track.get("creditsTrait") if isinstance(track, ObjectDict) else None
        people: object = trait.get("contributors") if isinstance(trait, ObjectDict) else None
        items: object = people.get("items") if isinstance(people, ObjectDict) else None

        if not isinstance(items, list):
            raise BaseClientError("Track credits response has no contributors list")

        return TrackCredits(
            resource.uri,
            tuple(from_dict(Credit, item) for item in cast(list[object], items)),
        )

    async def get_artist_top_tracks(self, uri: str, /) -> tuple[ArtistTopTrack, ...]:
        """Read Spotify's public top-track selection and play counts for an artist."""
        artist = await self.get_artist(uri)

        tracks = artist.discography.top_tracks if artist.discography else None

        return tuple(item.track for item in tracks.items) if tracks else ()

    async def get_profile(self, value: str, /, *, limit: int = 20) -> PublicProfile:
        """Read a public user's profile and first public playlists; no login needed."""
        _validate_page_limit(limit)

        resource = parse_spotify_resource(value, "user")

        data = await self.queries.get_json(
            f"https://spclient.wg.spotify.com/user-profile-view/v3/profile/{quote(resource.id, safe='')}",
            query={
                "playlist_limit": str(limit),
                "artist_limit": "0",
                "episode_limit": "0",
            },
        )

        try:
            return from_dict(PublicProfile, data)
        except (TypeError, ValueError) as exc:
            raise BaseClientError(f"Invalid public profile: {exc}") from exc

    async def get_artist(self, uri: str, /) -> ArtistDetails:
        """Fetch an artist profile and overview by Spotify URL, URI, or ID."""
        resource = parse_spotify_resource(uri, "artist")
        variables: dict[str, Any] = {
            "uri": resource.uri,
            "locale": "",
            "preReleaseV2": False,
            "includeMusicVideoPreviews": False,
        }

        response = await self.queries.query(Operations.QUERY_ARTIST_OVERVIEW.value, variables)

        data = Queries.resource_data(
            response,
            Operations.QUERY_ARTIST_OVERVIEW,
            ArtistDetails,
            resource.uri,
        )

        try:
            artist = from_dict(ArtistDetails, data)
        except (LookupError, TypeError, ValueError, AttributeError) as exc:
            raise BaseClientError(f"queryArtistOverview: invalid artist: {exc}") from exc

        if not (
            artist.id and artist.uri == resource.uri and artist.profile and artist.profile.name
        ):
            raise BaseClientError("queryArtistOverview: incomplete artist data")

        return artist

    async def get_album(self, uri: str, /) -> AlbumDetails:
        """Fetch album metadata and track information."""
        resource = parse_spotify_resource(uri, "album")

        album = await self.get_resource(resource.uri, Operations.GET_ALBUM, AlbumDetails)

        if not album.id or not album.name:
            raise BaseClientError("get_album returned incomplete album details")

        return album

    async def get_track(self, uri: str, /) -> TrackDetails:
        """Fetch track metadata by Spotify URL, URI, or ID."""
        resource = parse_spotify_resource(uri, "track")

        track = await self.get_resource(resource.uri, Operations.GET_TRACK, TrackDetails)

        if not track.id or not track.name:
            raise BaseClientError("get_track returned incomplete track details")

        return track

    async def get_tracks(self, tracks: Sequence[str], /) -> tuple[TrackDetails, ...]:
        """Fetch track details in input order with up to eight concurrent reads."""
        return await _get_many(tracks, "track", self.get_track)

    async def get_albums(self, albums: Sequence[str], /) -> tuple[AlbumDetails, ...]:
        """Fetch album details in input order with up to eight concurrent reads."""
        return await _get_many(albums, "album", self.get_album)

    async def get_artists(self, artists: Sequence[str], /) -> tuple[ArtistDetails, ...]:
        """Fetch artist details in input order with up to eight concurrent reads."""
        return await _get_many(artists, "artist", self.get_artist)

    async def get_podcast(self, uri: str, /) -> PodcastDetails:
        """Read podcast metadata from a URL, URI, or bare show ID."""
        show = await _show_details(uri, self.queries)

        if not isinstance(show, PodcastDetails):
            raise ValueError("This is an audiobook; use self.get_audiobook()")

        return show

    async def get_audiobook(self, uri: str, /) -> Audiobook:
        """Read audiobook metadata from its Spotify show link, URI or ID."""
        show = await _show_details(uri, self.queries)

        if not isinstance(show, Audiobook):
            raise ValueError("This is a podcast; use self.get_podcast()")

        return show

    async def get_podcast_episode(self, uri: str, /) -> PodcastEpisodeDetails:
        """Fetch a podcast episode by Spotify URL, URI, or ID."""
        resource = parse_spotify_resource(uri, "episode")

        episode = await self.get_resource(
            resource.uri,
            Operations.GET_EPISODE_OR_CHAPTER,
            PodcastEpisodeDetails,
        )

        if not episode.id or not episode.name or not episode.uri:
            raise BaseClientError("get_podcast_episode returned incomplete details")

        return episode

    def get_podcast_episodes(
        self,
        uri: str,
        /,
        *,
        limit: int = 50,
    ) -> AsyncGenerator[Sequence[PodcastEpisodeDetails], None]:
        """Stream a show's episodes in pages."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")

        resource = parse_spotify_resource(uri, "show")
        variables: dict[str, Any] = {
            "uri": resource.uri,
            "offset": 0,
            "limit": limit,
            "includeEpisodeContentRatingsV2": True,
        }

        return _show_pages(
            variables,
            self.queries,
            Operations.QUERY_PODCAST_EPISODES,
            "episodesV2",
            PodcastEpisodeDetails,
        )

    def get_audiobook_chapters(
        self, uri: str, /, *, limit: int = 50
    ) -> AsyncGenerator[Sequence[AudiobookChapter], None]:
        """Stream chapters in order, subject to Spotify's market availability."""
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("limit must be an integer between 1 and 100")

        book = parse_spotify_resource(uri, "show")

        return _show_pages(
            {"uri": book.uri, "offset": 0, "limit": limit},
            self.queries,
            Operations.QUERY_BOOK_CHAPTERS,
            "chaptersV2",
            AudiobookChapter,
        )

    async def iter_podcast_episodes(
        self,
        uri: str,
        /,
        *,
        limit: int = 50,
    ) -> AsyncGenerator[PodcastEpisodeDetails, None]:
        """Yield a show's episodes individually, hiding pagination details."""
        async with aclosing(self.get_podcast_episodes(uri, limit=limit)) as pages:
            async for page in pages:
                for episode in page:
                    yield episode
