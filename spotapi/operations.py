"""Names and options for Spotify persisted GraphQL queries."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final, Literal, TypeAlias

__all__ = (
    "DEFAULT_SEARCH_TYPES",
    "READ_OPERATIONS",
    "RESOURCE_KIND_ALIASES",
    "SEARCH_DESKTOP_SECTIONS",
    "SEARCH_KIND_ALIASES",
    "SEARCH_OPERATION_SECTIONS",
    "SEARCH_RESULT_FIELDS",
    "Operations",
    "ResourceInputKind",
    "ResourceKind",
    "SearchInputKind",
    "SearchKind",
    "SearchOptions",
    "normalize_resource_kind",
    "normalize_search_kind",
)


class Operations(StrEnum):
    """Persisted GraphQL operation names used by Spotify.

    Members are plain strings, so they can be passed anywhere an
    operation name is expected.
    """

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
    QUERY_TRACK_CREDITS_GROUPED_MODAL = "queryTrackCreditsGroupedModal"
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

    ADD_TO_LIBRARY = "addToLibrary"
    REMOVE_FROM_LIBRARY = "removeFromLibrary"
    PIN_LIBRARY_ITEM = "pinLibraryItem"
    UNPIN_LIBRARY_ITEM = "unpinLibraryItem"
    FOLLOW_USERS = "followUsers"
    UNFOLLOW_USERS = "unfollowUsers"
    ADD_TO_PLAYLIST = "addToPlaylist"
    REMOVE_FROM_PLAYLIST = "removeFromPlaylist"
    MOVE_ITEMS_IN_PLAYLIST = "moveItemsInPlaylist"


# Retry permission is explicit: unknown operations may be mutations even
# though they are sent to the same GraphQL query endpoint.
READ_OPERATIONS: Final[frozenset[Operations]] = frozenset(
    {
        Operations.ARE_ENTITIES_IN_LIBRARY,
        Operations.FETCH_LIBRARY_TRACKS,
        Operations.FETCH_PLAYLIST_CONTENTS,
        Operations.FETCH_PLAYLIST_METADATA,
        Operations.GET_ALBUM,
        Operations.GET_EPISODE_OR_CHAPTER,
        Operations.GET_PODCAST_OR_BOOK_NAME,
        Operations.GET_TRACK,
        Operations.IS_FOLLOWING_USERS,
        Operations.LIBRARY_V3,
        Operations.PROFILE_ATTRIBUTES,
        Operations.QUERY_ALBUM_TRACKS,
        Operations.QUERY_ARTIST_DISCOGRAPHY_ALBUMS,
        Operations.QUERY_ARTIST_DISCOGRAPHY_ALL,
        Operations.QUERY_ARTIST_DISCOGRAPHY_COMPILATIONS,
        Operations.QUERY_ARTIST_DISCOGRAPHY_SINGLES,
        Operations.QUERY_ARTIST_OVERVIEW,
        Operations.QUERY_ARTIST_RELATED,
        Operations.QUERY_BOOK_CHAPTERS,
        Operations.QUERY_PODCAST_EPISODES,
        Operations.QUERY_SHOW_METADATA_V2,
        Operations.QUERY_TRACK_CREDITS_GROUPED_MODAL,
        Operations.RECENTS,
        Operations.SEARCH_AUDIOBOOKS,
        Operations.SEARCH_AUTHORS,
        Operations.SEARCH_DESKTOP,
        Operations.SEARCH_EPISODES,
        Operations.SEARCH_GENRES,
        Operations.SEARCH_USERS,
        Operations.USER_TOP_CONTENT,
    }
)


ResourceKind: TypeAlias = Literal[
    "track",
    "album",
    "artist",
    "playlist",
    "show",
    "episode",
    "audiobook",
    "chapter",
    "user",
]
ResourceInputKind: TypeAlias = ResourceKind | Literal["podcast"]

SearchKind: TypeAlias = Literal[
    "track",
    "album",
    "artist",
    "playlist",
    "podcast",
    "audiobook",
    "episode",
    "author",
    "genre",
    "user",
]
SearchInputKind: TypeAlias = Literal[
    "track",
    "tracks",
    "album",
    "albums",
    "artist",
    "artists",
    "playlist",
    "playlists",
    "podcast",
    "podcasts",
    "show",
    "shows",
    "audiobook",
    "audiobooks",
    "book",
    "books",
    "episode",
    "episodes",
    "author",
    "authors",
    "genre",
    "genres",
    "user",
    "users",
]

# Spotify uses both ``show`` and the legacy ``podcast`` name for the same
# resource. Normalize at the boundary so internal dispatch stays unambiguous.
RESOURCE_KIND_ALIASES: Final[Mapping[str, ResourceKind]] = MappingProxyType(
    {
        "track": "track",
        "album": "album",
        "artist": "artist",
        "playlist": "playlist",
        "show": "show",
        "podcast": "show",
        "episode": "episode",
        "audiobook": "audiobook",
        "chapter": "chapter",
        "user": "user",
    }
)

SEARCH_KIND_ALIASES: Final[Mapping[str, SearchKind]] = MappingProxyType(
    {
        "track": "track",
        "tracks": "track",
        "album": "album",
        "albums": "album",
        "artist": "artist",
        "artists": "artist",
        "playlist": "playlist",
        "playlists": "playlist",
        "podcast": "podcast",
        "podcasts": "podcast",
        "show": "podcast",
        "shows": "podcast",
        "audiobook": "audiobook",
        "audiobooks": "audiobook",
        "book": "audiobook",
        "books": "audiobook",
        "episode": "episode",
        "episodes": "episode",
        "author": "author",
        "authors": "author",
        "genre": "genre",
        "genres": "genre",
        "user": "user",
        "users": "user",
    }
)

DEFAULT_SEARCH_TYPES: Final[tuple[SearchKind, ...]] = (
    "track",
    "artist",
    "album",
    "playlist",
    "podcast",
)

# A search-desktop response contains these categories together. The values
# are ordered fallbacks because Spotify has changed section names over time.
SEARCH_DESKTOP_SECTIONS: Final[Mapping[SearchKind, tuple[str, ...]]] = MappingProxyType(
    {
        "track": ("tracksV2", "tracks"),
        "artist": ("artists", "artistsV2"),
        "album": ("albums", "albumsV2"),
        "playlist": ("playlists", "playlistsV2"),
        "podcast": ("podcasts", "podcastsV2", "shows"),
        "episode": ("episodes",),
        "audiobook": ("audiobooks",),
        "user": ("users",),
        "author": ("authors",),
        "genre": ("genres",),
    }
)

SEARCH_OPERATION_SECTIONS: Final[Mapping[Operations, tuple[str, ...]]] = MappingProxyType(
    {
        Operations.SEARCH_TRACKS: SEARCH_DESKTOP_SECTIONS["track"],
        Operations.SEARCH_ARTISTS: SEARCH_DESKTOP_SECTIONS["artist"],
        Operations.SEARCH_ALBUMS: SEARCH_DESKTOP_SECTIONS["album"],
        Operations.SEARCH_PLAYLISTS: SEARCH_DESKTOP_SECTIONS["playlist"],
        Operations.SEARCH_PODCASTS: SEARCH_DESKTOP_SECTIONS["podcast"],
        Operations.SEARCH_EPISODES: SEARCH_DESKTOP_SECTIONS["episode"],
        Operations.SEARCH_AUDIOBOOKS: SEARCH_DESKTOP_SECTIONS["audiobook"],
        Operations.SEARCH_USERS: SEARCH_DESKTOP_SECTIONS["user"],
        Operations.SEARCH_AUTHORS: SEARCH_DESKTOP_SECTIONS["author"],
        Operations.SEARCH_GENRES: SEARCH_DESKTOP_SECTIONS["genre"],
    }
)

SEARCH_RESULT_FIELDS: Final[Mapping[SearchKind, str]] = MappingProxyType(
    {
        "track": "tracks",
        "album": "albums",
        "artist": "artists",
        "playlist": "playlists",
        "podcast": "podcasts",
        "audiobook": "audiobooks",
        "episode": "episodes",
        "author": "authors",
        "genre": "genres",
        "user": "users",
    }
)


def normalize_resource_kind(value: str) -> ResourceKind:
    """Return Spotify's canonical resource kind for an input alias.

    Args:
        value: Resource type from a URL, URI, or explicit ``kind`` argument.

    Returns:
        The canonical Spotify resource kind.

    Raises:
        ValueError: If ``value`` is not a supported resource type.
    """
    try:
        return RESOURCE_KIND_ALIASES[value.casefold()]
    except KeyError:
        supported = ", ".join(RESOURCE_KIND_ALIASES)
        raise ValueError(
            f"Unsupported Spotify resource type {value!r}; expected one of: {supported}"
        ) from None


def normalize_search_kind(value: str) -> SearchKind:
    """Return the canonical search kind for a singular or plural alias.

    Args:
        value: Entity category such as ``"track"``, ``"tracks"``, or ``"show"``.

    Returns:
        The canonical search kind.

    Raises:
        ValueError: If ``value`` is not a supported search category.
    """
    try:
        return SEARCH_KIND_ALIASES[value.casefold()]
    except KeyError:
        supported = ", ".join(SEARCH_KIND_ALIASES)
        raise ValueError(
            f"Unsupported Spotify search type {value!r}; expected one of: {supported}"
        ) from None


@dataclass(slots=True, frozen=True)
class SearchOptions:
    """Advanced inclusion options for catalogue search.

    Python field names remain independent of Spotify's GraphQL variables.
    Pass this object as ``options=`` to search methods. Their explicit ``limit``
    argument overrides this object's page size without modifying it.

    Attributes:
        limit: Results per category or page, from 1 to 100.
        number_of_top_results: Maximum top-result entries requested from Spotify.
        include_audiobooks: Request audiobook metadata.
        include_artist_has_concerts_field: Request artist concert availability.
        include_pre_releases: Request pre-release metadata.
        include_album_pre_releases: Request pre-release albums.
        include_authors: Request audiobook authors.
        include_episode_content_ratings_v2: Request episode content ratings.
    """

    limit: int = 100
    number_of_top_results: int = 20
    include_audiobooks: bool = False
    include_artist_has_concerts_field: bool = False
    include_pre_releases: bool = False
    include_album_pre_releases: bool = False
    include_authors: bool = False
    include_episode_content_ratings_v2: bool = False

    def to_variables(self) -> dict[str, int | bool]:
        """Return native GraphQL variables without exposing wire names as attributes."""
        return {
            "limit": self.limit,
            "numberOfTopResults": self.number_of_top_results,
            "includeAudiobooks": self.include_audiobooks,
            "includeArtistHasConcertsField": self.include_artist_has_concerts_field,
            "includePreReleases": self.include_pre_releases,
            "includeAlbumPreReleases": self.include_album_pre_releases,
            "includeAuthors": self.include_authors,
            "includeEpisodeContentRatingsV2": self.include_episode_content_ratings_v2,
        }
