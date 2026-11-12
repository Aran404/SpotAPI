"""Typed Spotify response models and the public dataclass decoder export."""

from __future__ import annotations

from spotapi._decoding import from_dict

from .album import Album
from .album_details import AlbumDetails
from .artist import Artist
from .artist_details import ArtistDetails
from .common import (
    ColorDark,
    ExtractedColors,
    ExtractedColorSet,
    Sources,
    SquareCoverImage,
    VisualIdentity,
)
from .entities import (
    Audiobook,
    Author,
    Episode,
    Genre,
    PodcastDetails,
    PublicProfile,
    User,
)
from .playlist import Playlist
from .playlist_details import PlaylistDetails, PlaylistEntry
from .playlist_track import PlaylistTrack
from .podcast import Podcast
from .podcast_episode import PodcastEpisodeDetails
from .profile_attributes import Profile
from .track import Track
from .track_details import TrackDetails

__all__ = (
    "Album",
    "AlbumDetails",
    "Artist",
    "ArtistDetails",
    "Audiobook",
    "Author",
    "ColorDark",
    "Episode",
    "ExtractedColorSet",
    "ExtractedColors",
    "Genre",
    "Playlist",
    "PlaylistDetails",
    "PlaylistEntry",
    "PlaylistTrack",
    "Podcast",
    "PodcastDetails",
    "PodcastEpisodeDetails",
    "Profile",
    "PublicProfile",
    "Sources",
    "SquareCoverImage",
    "Track",
    "TrackDetails",
    "User",
    "VisualIdentity",
    "from_dict",
)
