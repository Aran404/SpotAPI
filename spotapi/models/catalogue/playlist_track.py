"""Playlist track response models."""

from __future__ import annotations

from dataclasses import dataclass

from .common import Sources
from .track import (
    Artists,
    ContentRating,
    Duration,
    Playability,
)

__all__ = ("PlaylistTrack",)


@dataclass(slots=True)
class PlaylistTrackCoverArt:
    sources: list[Sources]


@dataclass(slots=True)
class PlaylistTrackAlbum:
    cover_art: PlaylistTrackCoverArt
    name: str
    uri: str

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]


@dataclass(slots=True)
class CamelotKey:
    value: str | None = None
    color: str | None = None


@dataclass(slots=True)
class MusicalKey:
    """Optional pitch, mode and Camelot metadata supplied by Spotify.

    Missing values are left unknown; no harmonic analysis is inferred locally.
    """

    key: str | None = None
    mode: str | None = None
    camelot_key: CamelotKey | None = None


@dataclass(slots=True)
class PlaylistAudioAttributes:
    bpm: float | None = None
    key: MusicalKey | None = None


@dataclass(slots=True)
class PlaylistTrack:
    """Available music metadata for one playlist occurrence's track.

    ``bpm``, ``musical_key`` and ``camelot_key`` expose optional Spotify analysis.
    ``duration`` exposes the shared duration model. Occurrence identity lives in
    the containing PlaylistEntry, not in the track URI.
    """

    name: str
    uri: str
    album_of_track: PlaylistTrackAlbum | None = None
    artists: Artists | None = None
    content_rating: ContentRating | None = None
    media_type: str | None = None
    playability: Playability | None = None
    track_duration: Duration | None = None
    playcount: str | None = None
    playlist_audio_attributes: PlaylistAudioAttributes | None = None

    @property
    def bpm(self) -> float | None:
        """Tempo when Spotify supplies playlist audio metadata."""
        return self.playlist_audio_attributes.bpm if self.playlist_audio_attributes else None

    @property
    def musical_key(self) -> MusicalKey | None:
        """Return the supplied musical key, without inferring missing analysis."""
        return self.playlist_audio_attributes.key if self.playlist_audio_attributes else None

    @property
    def camelot_key(self) -> str | None:
        """Return Spotify's supplied Camelot key, or None."""
        key = self.musical_key

        return key.camelot_key.value if key and key.camelot_key else None

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]

    @property
    def duration(self) -> Duration | None:
        """Expose playlist track duration using the shared track-model interface."""
        return self.track_duration

    @property
    def track_media_type(self) -> str | None:
        """Expose playlist media type using the shared track-model interface."""
        return self.media_type

    def __repr__(self) -> str:
        if self.artists is None:
            artists = ""
        else:
            artists = ", ".join(
                artist.profile.name for artist in self.artists.items if artist.profile is not None
            )

        return f"<PlaylistTrack id={self.id!r} name={self.name!r} artists={artists!r}>"
