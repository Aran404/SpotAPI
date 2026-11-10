"""Typed catalogue, playback and lyrics results for application code."""

from .v2.account import AccountChallenge, AccountPlan, AccountProfile, ProfileValidationError
from .v2.blend import BlendInvitation
from .v2.discovery import Canvas, RecommendedTrack
from .v2.history import RecentItem
from .v2.library_models import LibraryItem, LibraryOption, LibraryPage, SavedTrack
from .v2.lyrics import LyricLine, Lyrics, LyricSyllable
from .v2.notifications import Notification, NotificationPage
from .v2.playback import Device, PlaybackQuality, PlaybackTrack, PlaybackUpdate, PlayerState
from .v2.profiles import ProfilePlaylists
from .v2.specialized.data_wrappers import (
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
from .v2.specialized.data_wrappers.album_details import AlbumTrack
from .v2.specialized.data_wrappers.artist_details import (
    ArtistRelatedArtist,
    ArtistRelease,
    ArtistTopTrack,
)
from .v2.specialized.data_wrappers.catalogue import ProfilePlaylist
from .v2.specialized.data_wrappers.credits import Credit, TrackCredits
from .v2.specialized.data_wrappers.playlist_track import MusicalKey
from .v2.stats import TimeRange, TopContent

__all__ = (
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
