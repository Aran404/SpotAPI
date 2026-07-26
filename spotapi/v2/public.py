from __future__ import annotations

from enum import Enum
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, AsyncGenerator, Final, TypeVar

from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.specialized.data_wrappers import *
from spotapi.v2.query import QueryClient, QueryClientPool

if TYPE_CHECKING:
    from collections.abc import Sequence


__all__: tuple[str, ...] = (
    "InclusionParameters",
    "Operations",
    "Public",
    "QueryWrapper",
    "Podcast",
    "Artist",
    "Playlist",
    "Track",
    "Album",
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
    QUERY_ALBUM_TRACK_URIS = "queryAlbumTrackUris"
    QUERY_TRACK_ARTISTS = "queryTrackArtists"
    GET_ALBUM = "getAlbum"
    QUERY_ALBUM_TRACKS = "queryAlbumTracks"
    QUERY_ARTIST_OVERVIEW = "queryArtistOverview"
    QUERY_ARTIST_APPEARS_ON = "queryArtistAppearsOn"
    QUERY_ARTIST_DISCOGRAPHY_ALBUMS = "queryArtistDiscographyAlbums"
    QUERY_ARTIST_DISCOGRAPHY_SINGLES = "queryArtistDiscographySingles"
    QUERY_ARTIST_DISCOGRAPHY_COMPILATIONS = "queryArtistDiscographyCompilations"
    QUERY_ARTIST_DISCOGRAPHY_ALL = "queryArtistDiscographyAll"
    QUERY_ARTIST_DISCOGRAPHY_OVERVIEW = "queryArtistDiscographyOverview"
    QUERY_ARTIST_DISCOVERED_ON = "queryArtistDiscoveredOn"
    QUERY_ARTIST_FEATURING = "queryArtistFeaturing"
    QUERY_ARTIST_PLAYLISTS = "queryArtistPlaylists"
    QUERY_ARTIST_RELATED = "queryArtistRelated"
    QUERY_ARTIST_RELATED_VIDEOS = "queryArtistRelatedVideos"
    QUERY_ARTIST_MINIMAL = "queryArtistMinimal"
    ARTIST_CONCERTS = "ArtistConcerts"
    ARTIST_CONCERTS_PAGE_LOCATION = "ArtistConcertsPageLocation"
    CANVAS = "canvas"
    INFERRED_USER_LOCATION = "inferredUserLocation"
    HOME = "home"
    HOME_SECTION = "homeSection"
    HOME_PINNED_SECTIONS = "homePinnedSections"
    EPISODE_SPONSORED_CONTENT = "episodeSponsoredContent"
    NPV_PAGE_CONTENT = "npvPageContent"
    QUERY_NPV_EPISODE = "queryNpvEpisode"
    QUERY_NPV_ARTIST = "queryNpvArtist"
    RECENT_SEARCHES = "recentSearches"
    GET_VIDEO_TRACK_ASSOCIATED_ALBUM = "getVideoTrackAssociatedAlbum"
    GET_TRACK = "getTrack"
    QUERY_WHATS_NEW_FEED = "queryWhatsNewFeed"
    WHATS_NEW_FEED_NEW_ITEMS = "whatsNewFeedNewItems"
    GET_ALBUM_NAME_AND_TRACKS = "getAlbumNameAndTracks"
    GET_ARTIST_NAME_AND_TRACKS = "getArtistNameAndTracks"
    GET_COMMENTS_FOR_ENTITY = "getCommentsForEntity"
    GET_REACTIONS = "getReactions"
    GET_REPLIES = "getReplies"
    ASSISTED_CURATION_SEARCH = "assistedCurationSearch"
    ASSISTED_CURATION_SEARCH_ALBUM = "assistedCurationSearchAlbum"
    ASSISTED_CURATION_SEARCH_ARTIST = "assistedCurationSearchArtist"
    IS_FOLLOWING_USERS = "isFollowingUsers"
    DECORATE_CONTEXT_EPISODES_OR_CHAPTERS = "decorateContextEpisodesOrChapters"
    DECORATE_CONTEXT_TRACKS = "decorateContextTracks"
    RECENTS = "recents"
    IS_CURATED = "isCurated"
    EDITABLE_PLAYLISTS = "editablePlaylists"
    IS_CURATED_ENTITIES = "isCuratedEntities"
    LIBRARY_V3 = "libraryV3"
    ARE_ENTITIES_IN_LIBRARY = "areEntitiesInLibrary"
    FETCH_LIBRARY_TRACKS = "fetchLibraryTracks"
    FETCH_PLAYLIST = "fetchPlaylist"
    FETCH_PLAYLIST_METADATA = "fetchPlaylistMetadata"
    FETCH_PLAYLIST_CONTENTS = "fetchPlaylistContents"
    GET_LISTS = "getLists"
    GET_LISTS_METADATA = "getListsMetadata"
    GET_LISTS_CONTENTS = "getListsContents"
    PLAYLIST_PERMISSIONS = "playlistPermissions"
    ACCOUNT_ATTRIBUTES = "accountAttributes"
    FETCH_ENTITIES_FOR_RECENTLY_PLAYED = "fetchEntitiesForRecentlyPlayed"
    QUERY_SHOW_METADATA_V2 = "queryShowMetadataV2"
    QUERY_BOOK_CHAPTERS = "queryBookChapters"
    GET_EPISODE_OR_CHAPTER = "getEpisodeOrChapter"
    QUERY_PODCAST_EPISODES = "queryPodcastEpisodes"
    CENTRALISED_STATE_PLAYER_OPTIONS = "centralisedStatePlayerOptions"
    SMART_SHUFFLE = "smartShuffle"
    PROFILE_ATTRIBUTES = "profileAttributes"
    FETCH_EXTRACTED_COLORS = "fetchExtractedColors"
    GET_DYNAMIC_COLORS = "getDynamicColors"
    GET_DYNAMIC_COLORS_BY_URIS = "getDynamicColorsByUris"
    GET_EPISODE_NAME = "getEpisodeName"
    GET_PODCAST_OR_BOOK_NAME = "getPodcastOrBookName"
    GET_TRACK_NAME = "getTrackName"
    SEO_RECOMMENDED_TRACK_PLAYLIST_DESKTOP = "seoRecommendedTrackPlaylistDesktop"
    SIMILAR_ALBUMS_BASED_ON_THIS_TRACK = "similarAlbumsBasedOnThisTrack"
    CONCERT_COUNT = "concertCount"
    CONCERT_LOCATIONS_BY_LAT_LON = "concertLocationsByLatLon"
    USER_LOCATION = "userLocation"
    BROWSE_SECTION = "browseSection"
    BROWSE_PAGE = "browsePage"
    LOOKUP_ENTITY_IMAGES = "lookupEntityImages"
    CONCERT = "concert"
    QUERY_TRACK_CREDITS_MODAL = "queryTrackCreditsModal"
    FETCH_EXTRACTED_COLOR_AND_IMAGE_FOR_ALBUM_ENTITY = "fetchExtractedColorAndImageForAlbumEntity"
    FETCH_EXTRACTED_COLOR_AND_IMAGE_FOR_ARTIST_ENTITY = (
        "fetchExtractedColorAndImageForArtistEntity"
    )
    FETCH_EXTRACTED_COLOR_AND_IMAGE_FOR_EPISODE_ENTITY = (
        "fetchExtractedColorAndImageForEpisodeEntity"
    )
    FETCH_EXTRACTED_COLOR_AND_IMAGE_FOR_PLAYLIST_ENTITY = (
        "fetchExtractedColorAndImageForPlaylistEntity"
    )
    FETCH_EXTRACTED_COLOR_AND_IMAGE_FOR_PODCAST_ENTITY = (
        "fetchExtractedColorAndImageForPodcastEntity"
    )
    FETCH_EXTRACTED_COLOR_AND_IMAGE_FOR_TRACK_ENTITY = "fetchExtractedColorAndImageForTrackEntity"
    FETCH_EXTRACTED_COLOR_FOR_ALBUM_ENTITY = "fetchExtractedColorForAlbumEntity"
    FETCH_EXTRACTED_COLOR_FOR_ARTIST_ENTITY = "fetchExtractedColorForArtistEntity"
    FETCH_EXTRACTED_COLOR_FOR_EPISODE_ENTITY = "fetchExtractedColorForEpisodeEntity"
    FETCH_EXTRACTED_COLOR_FOR_PLAYLIST_ENTITY = "fetchExtractedColorForPlaylistEntity"
    FETCH_EXTRACTED_COLOR_FOR_PODCAST_ENTITY = "fetchExtractedColorForPodcastEntity"
    FETCH_EXTRACTED_COLOR_FOR_TRACK_ENTITY = "fetchExtractedColorForTrackEntity"
    SHOW_ITEMS_PLAYED_STATE = "showItemsPlayedState"
    CONCERT_ROUTING_CARD_VISUALS = "concertRoutingCardVisuals"
    BROWSE_ALL = "browseAll"
    COUNTRY_HUB_CONTENT = "countryHubContent"
    INTERNAL_LINK_RECOMMENDER_SHOW = "internalLinkRecommenderShow"
    SIMILAR_AUDIOBOOKS = "similarAudiobooks"
    COUNTRY_HUBS_PAGE = "countryHubsPage"
    TRACK_PREVIEW = "trackPreview"
    NPV_V2_TRACK_SUPPLEMENTAL_SECTIONS = "npvV2TrackSupplementalSections"
    DECORATE_QUEUED_BY_USERS = "decorateQueuedByUsers"
    ALBUM_PRE_RELEASE_TRACKS = "albumPreReleaseTracks"
    ALBUM_PRE_RELEASE = "albumPreRelease"
    CONCERT_CONCEPTS = "concertConcepts"
    CONCERT_FEED = "concertFeed"
    CONCERT_LOCATION_DETAILS = "concertLocationDetails"
    USER_TOP_CONTENT = "userTopContent"
    USER_ACCOUNT_ID = "userAccountId"
    VENUE = "venue"
    LOOKUP_DEBUG = "lookupDebug"
    WATCH_FEED_VIEW = "watchFeedView"
    WATCH_FEED_ENTITY = "watchFeedEntity"
    QUERY_ALBUM_MERCH = "queryAlbumMerch"
    CONCERT_GALLERY = "ConcertGallery"
    THISIS_PLAYLIST_EXTENSION = "thisisPlaylistExtension"
    QUERY_INLINE_CURATION_SEARCH_V2 = "queryInlineCurationSearchV2"
    QUERY_INLINE_CURATION_SEARCH_V2_BOOKLISTS = "queryInlineCurationSearchV2Booklists"
    QUERY_INLINE_CURATION_SEARCH_ALBUM = "queryInlineCurationSearchAlbum"
    QUERY_INLINE_CURATION_SEARCH_ARTIST = "queryInlineCurationSearchArtist"
    PLAYLIST_SECTION = "playlistSection"
    INTERNAL_LINK_RECOMMENDER_TRACK = "internalLinkRecommenderTrack"
    CONCERT_CAMPAIGN = "ConcertCampaign"


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

    def __init__(self, bc: QueryClient) -> None:
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

    async def direct_query(
        self,
        uri: str,
        /,
        operation: Operations,
        *,
        obey_total_count: bool = True,
    ) -> AsyncGenerator[ObjectDict]:
        variables: dict[str, Any] = {
            "uri": uri,
            "locale": "",
            "offset": 0,
            "limit": 100,
        }

        return self._bc.paginate_query(
            variables,
            operation.value,
            obey_total_count=obey_total_count,
            return_raw=True,
        )

    async def typed_search(
        self,
        typ: type[_SearchResultT],
        op: Operations,
        query: str,
        /,
    ) -> AsyncGenerator[Sequence[_SearchResultT]]:
        gen = await self.search(query, operation=op)
        try:
            async for raw in gen:
                results: list[_SearchResultT] = []
                for item in raw._items:
                    data = self.extract_data(item)
                    results.append(from_dict(typ, data))
                yield results
        finally:
            await gen.aclose()


class Public:
    """Provides access to Spotify's public search endpoints.

    This class exposes asynchronous generators for searching queries
    without requiring user authentication.

    All search methods yield pages of results as they are retrieved
    from Spotify.

    Use :meth:`anext` for non-paginated results.
    """

    __slots__ = ()

    @staticmethod
    async def search(
        typ: type[_SearchResultT],
        op: Operations,
        query: str,
        /,
    ) -> AsyncGenerator[Sequence[_SearchResultT]]:
        bc = await QueryClientPool.get()
        gen = QueryWrapper(bc).typed_search(typ, op, query)
        try:
            async for typed in gen:
                yield typed
        finally:
            QueryClientPool.put(bc)

    @staticmethod
    async def get_resource(uri: str, operation: Operations, /) -> AsyncGenerator[ObjectDict]:
        if not uri.startswith("spotify:"):
            raise ValueError(f"Invalid URI: {uri}")

        bc = await QueryClientPool.get()
        gen = await QueryWrapper(bc).direct_query(uri, operation=operation)

        try:
            async for page in gen:
                yield page
        finally:
            QueryClientPool.put(bc)

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

    # TODO: Good first issue, annotate the return types so they aren't generic like above.

    @staticmethod
    async def get_album(uri: str, /) -> AsyncGenerator[ObjectDict]:
        uri = f"spotify:album:{uri}" if not uri.startswith("spotify:album:") else uri
        async for page in Public.get_resource(uri, Operations.GET_ALBUM):
            yield page

    @staticmethod
    async def get_track(uri: str, /) -> AsyncGenerator[ObjectDict]:
        uri = f"spotify:track:{uri}" if not uri.startswith("spotify:track:") else uri
        async for page in Public.get_resource(uri, Operations.GET_TRACK):
            yield page

    @staticmethod
    async def get_podcast(uri: str, /) -> AsyncGenerator[ObjectDict]:
        uri = f"spotify:podcast:{uri}" if not uri.startswith("spotify:podcast:") else uri
        async for page in Public.get_resource(uri, Operations.GET_PODCAST_OR_BOOK_NAME):
            yield page

    # TODO: search_users, search_audiobooks, search_desktops, etc...
