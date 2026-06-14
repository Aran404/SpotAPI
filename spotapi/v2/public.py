from __future__ import annotations

from enum import Enum
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator, Final, TypeVar

from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.specialized.data_wrappers import *
from spotapi.v2.base import BaseClient, BaseClientPool

if TYPE_CHECKING:
    from collections.abc import Sequence


__all__: tuple[str, ...] = (
    "InclusionParameters",
    "Operations",
    "Public",
    "QueryWrapper",
)


class Operations(str, Enum):
    SEARCH_TRACKS = "searchTracks"
    SEARCH_ALBUMS = "searchAlbums"
    SEARCH_ARTISTS = "searchArtists"
    SEARCH_AUTHORS = "searchAuthors"
    SEARCH_AUDIOBOOKS = "searchAudiobooks"
    SEARCH_EPISODES = "searchEpisodes"
    SEARCH_FULL_EPISODES = "searchFullEpisodes"
    SEARCH_GENRES = "searchGenres"
    SEARCH_PLAYLISTS = "searchPlaylists"
    SEARCH_PODCASTS = "searchPodcasts"
    SEARCH_USERS = "searchUsers"
    SEARCH_TOP_RESULTS = "searchTopResults"
    SEARCH_TOP_RESULTS_ONLY = "searchTopResultsOnly"
    SEARCH_TOP_RESULTS_LIST = "searchTopResultsList"
    SEARCH_PODCAST_AND_EPISODES = "searchPodcastAndEpisodes"
    SEARCH_CONCERT_LOCATIONS = "searchConcertLocations"
    SEARCH_SUGGESTIONS = "searchSuggestions"
    SEARCH_DESKTOP = "searchDesktop"
    SEARCH_MODAL_ENTITY_PAGE = "searchModalEntityPage"
    SEARCH_MODAL_RESULTS = "searchModalResults"


@dataclass(slots=True)
class InclusionParameters:
    limit: int = 100
    numberOfTopResults: int = 20
    includeAudiobooks: bool = False
    includeArtistHasConcertsField: bool = False
    includePreReleases: bool = False
    includeAlbumPreReleases: bool = False
    includeAuthors: bool = False
    includeEpisodeContentRatingsV2: bool = False


_DEFAULT_PARAMETERS: Final[dict[str, Any]] = asdict(InclusionParameters())
_SearchResultT = TypeVar("_SearchResultT")


class QueryWrapper:
    __slots__: tuple[str, ...] = ("_bc",)

    def __init__(self, bc: BaseClient) -> None:
        self._bc = bc

    @staticmethod
    def extract_data(item: ObjectDict) -> ObjectDict:
        if "data" in item:
            return item["data"]

        for value in item.values():
            if isinstance(value, dict) and "data" in value:
                return value["data"]  # type: ignore[value]

        return item

    async def search(
        self,
        query: str,
        /,
        operation: Operations,
        *,
        obey_total_count: bool = True,
        parameters: InclusionParameters | None = None,
    ) -> AsyncGenerator[ObjectDict]:
        variables: dict[str, Any] = {
            "searchTerm": query,
            "offset": 0,
            **(asdict(parameters) if parameters is not None else _DEFAULT_PARAMETERS),
            "isPrefix": None,
            "sectionFilters": ["GENERIC"],
        }

        return self._bc.paginate_query(
            variables,
            operation.value,
            obey_total_count=obey_total_count,
        )


class Public:
    __slots__ = ()

    @staticmethod
    async def search(
        typ: type[_SearchResultT],
        op: Operations,
        query: str,
        /,
    ) -> AsyncGenerator[Sequence[_SearchResultT]]:
        bc = await BaseClientPool.get()
        qw = QueryWrapper(bc)

        gen = await qw.search(query, operation=op)
        try:
            async for raw in gen:
                results: list[_SearchResultT] = []
                for item in raw._items:
                    data = qw.extract_data(item)
                    results.append(from_dict(typ, data))
                yield results
        finally:
            await gen.aclose()
            BaseClientPool.put(bc)

    @staticmethod
    async def search_tracks(query: str, /) -> AsyncGenerator[Sequence[Track]]:
        async for page in Public.search(Track, Operations.SEARCH_TRACKS, query):
            yield page

    @staticmethod
    async def search_playlists(query: str, /) -> AsyncGenerator[Sequence[Playlist]]:
        async for page in Public.search(Playlist, Operations.SEARCH_PLAYLISTS, query):
            yield page

    @staticmethod
    async def search_artists(query: str, /) -> AsyncGenerator[Sequence[Artist]]:
        async for page in Public.search(Artist, Operations.SEARCH_ARTISTS, query):
            yield page

    @staticmethod
    async def search_podcasts(query: str, /) -> AsyncGenerator[Sequence[Podcast]]:
        async for page in Public.search(Podcast, Operations.SEARCH_PODCASTS, query):
            yield page

    @staticmethod
    async def search_albums(query: str, /) -> AsyncGenerator[Sequence[Album]]:
        async for page in Public.search(Album, Operations.SEARCH_ALBUMS, query):
            yield page

    # search_users, search_audiobooks, search_desktops, etc...
