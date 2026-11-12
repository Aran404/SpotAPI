"""Typed catalogue, playback and lyrics results for application code."""

from spotapi.resources import SpotifyResource

from .account import AccountChallenge, AccountPlan, AccountProfile, ProfileValidationError
from .blend import BlendInvitation
from .catalogue import (
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
    Profile,
    PublicProfile,
    Track,
    TrackDetails,
    User,
)
from .catalogue.album_details import AlbumTrack
from .catalogue.artist_details import (
    ArtistRelatedArtist,
    ArtistRelease,
    ArtistTopTrack,
)
from .catalogue.credits import Credit, TrackCredits
from .catalogue.entities import AudiobookChapter, ProfilePlaylist
from .catalogue.playlist_track import MusicalKey
from .discovery import Canvas, RecommendedTrack
from .history import RecentItem
from .library import LibraryItem, LibraryOption, LibraryPage, SavedTrack
from .lyrics import LyricLine, Lyrics, LyricSyllable
from .notifications import Notification, NotificationPage
from .playback import Device, PlaybackQuality, PlaybackTrack, PlaybackUpdate, PlayerState
from .profiles import ProfilePlaylists
from .search import SearchResults
from .stats import TimeRange, TopContent

__all__ = (
    "AccountChallenge",
    "AccountPlan",
    "AccountProfile",
    "Album",
    "AlbumDetails",
    "AlbumTrack",
    "Artist",
    "ArtistDetails",
    "ArtistRelatedArtist",
    "ArtistRelease",
    "ArtistTopTrack",
    "Audiobook",
    "AudiobookChapter",
    "Author",
    "BlendInvitation",
    "Canvas",
    "Credit",
    "Device",
    "Episode",
    "Genre",
    "LibraryItem",
    "LibraryOption",
    "LibraryPage",
    "LyricLine",
    "LyricSyllable",
    "Lyrics",
    "MusicalKey",
    "Notification",
    "NotificationPage",
    "PlaybackQuality",
    "PlaybackTrack",
    "PlaybackUpdate",
    "PlayerState",
    "Playlist",
    "PlaylistDetails",
    "PlaylistEntry",
    "PlaylistTrack",
    "Podcast",
    "PodcastDetails",
    "PodcastEpisodeDetails",
    "Profile",
    "ProfilePlaylist",
    "ProfilePlaylists",
    "ProfileValidationError",
    "PublicProfile",
    "RecentItem",
    "RecommendedTrack",
    "SavedTrack",
    "SearchResults",
    "SpotifyResource",
    "TimeRange",
    "TopContent",
    "Track",
    "TrackCredits",
    "TrackDetails",
    "User",
)
