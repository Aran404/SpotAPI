from __future__ import annotations

from dataclasses import dataclass

from spotapi.v2.specialized.data_wrappers.common import (
    CoverArt as _CoverArt,
    VisualIdentity,
)

__all__: tuple[str, ...] = ("Track",)


@dataclass(slots=True)
class CoverArt(_CoverArt):
    """Album cover art — inherits extracted colors and sources from the common base."""


@dataclass(slots=True)
class AlbumOfTrack:
    cover_art: CoverArt
    id: str
    name: str
    uri: str
    visual_identity: VisualIdentity


@dataclass(slots=True)
class ArtistProfile:
    name: str


@dataclass(slots=True)
class ArtistItem:
    profile: ArtistProfile
    uri: str


@dataclass(slots=True)
class Artists:
    items: list[ArtistItem]


@dataclass(slots=True)
class AudioAssociations:
    total_count: int


@dataclass(slots=True)
class VideoAssociations:
    total_count: int


@dataclass(slots=True)
class AssociationsV3:
    audio_associations: AudioAssociations
    video_associations: VideoAssociations


@dataclass(slots=True)
class ContentRating:
    label: str


@dataclass(slots=True)
class Duration:
    total_milliseconds: int


@dataclass(slots=True)
class Playability:
    playable: bool
    reason: str


@dataclass(slots=True)
class Track:
    """A Spotify track returned by the search API.

    Attributes
    ----------
    id : str
        The Spotify track ID.
    name : str
        Human-readable track title.
    uri : str
        Spotify URI (``spotify:track:<id>``).
    duration : Duration
        Total track length in milliseconds.
    artists : Artists
        Collection of credited artists.
    album_of_track : AlbumOfTrack
        The album this track belongs to, with cover art.
    playability : Playability
        Whether the track can be played in the current market.
    track_media_type : str
        ``"AUDIO"`` or ``"VIDEO"``.
    """

    album_of_track: AlbumOfTrack
    artists: Artists
    associations_v3: AssociationsV3
    content_rating: ContentRating
    duration: Duration
    id: str
    track_media_type: str
    name: str
    playability: Playability
    uri: str
    visual_identity: VisualIdentity

    def __repr__(self) -> str:
        artist_names = ", ".join(a.profile.name for a in (self.artists.items or []))
        return f"<Track id={self.id!r} name={self.name!r} artists={artist_names!r}>"
