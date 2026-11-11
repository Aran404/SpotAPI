"""Typed catalogue, playback and lyrics results for application code."""

from .account import AccountChallenge, AccountPlan, AccountProfile, ProfileValidationError
from .blend import BlendInvitation
from .discovery import Canvas, RecommendedTrack
from .history import RecentItem
from .library_models import LibraryItem, LibraryOption, LibraryPage, SavedTrack
from .lyrics import LyricLine, Lyrics, LyricSyllable
from .notifications import Notification, NotificationPage
from .playback import Device, PlaybackQuality, PlaybackTrack, PlaybackUpdate, PlayerState
from .profiles import ProfilePlaylists
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
)
from .specialized.data_wrappers.album_details import AlbumTrack
from .specialized.data_wrappers.artist_details import (
    ArtistRelatedArtist,
    ArtistRelease,
    ArtistTopTrack,
)
from .specialized.data_wrappers.catalogue import AudiobookChapter, ProfilePlaylist
from .specialized.data_wrappers.credits import Credit, TrackCredits
from .specialized.data_wrappers.playlist_track import MusicalKey
from .stats import TimeRange, TopContent

__all__ = (
    "AudiobookChapter",
    "AccountChallenge",
    "AccountPlan",
    "AccountProfile",
    "ProfileValidationError",
    "BlendInvitation",
    "Canvas",
    "RecommendedTrack",
    "LibraryItem",
    "LibraryOption",
    "LibraryPage",
    "SavedTrack",
    "Notification",
    "NotificationPage",
    "ProfilePlaylists",
    "ProfilePlaylist",
    "TimeRange",
    "TopContent",
    "RecentItem",
    "Device",
    "PlaybackTrack",
    "PlaybackQuality",
    "PlayerState",
    "PlaybackUpdate",
    "Lyrics",
    "LyricLine",
    "LyricSyllable",
    "ArtistRelease",
    "Credit",
    "TrackCredits",
    "Album",
    "AlbumDetails",
    "AlbumTrack",
    "Artist",
    "ArtistDetails",
    "ArtistRelatedArtist",
    "ArtistTopTrack",
    "Audiobook",
    "Author",
    "Episode",
    "Genre",
    "MusicalKey",
    "Playlist",
    "PlaylistDetails",
    "PlaylistEntry",
    "PlaylistTrack",
    "Podcast",
    "PodcastDetails",
    "PodcastEpisodeDetails",
    "PublicProfile",
    "Track",
    "TrackDetails",
    "User",
)
