"""Typed track results from Spotify search."""

from __future__ import annotations

from dataclasses import dataclass, field

from .common import (
    CoverArt,
    VisualIdentity,
)

__all__ = ("Track",)


@dataclass(slots=True)
class AlbumOfTrack:
    """Album metadata embedded in a search hit."""

    id: str
    name: str
    uri: str
    cover_art: CoverArt | None = None
    visual_identity: VisualIdentity | None = None


@dataclass(slots=True)
class ArtistProfile:
    name: str


@dataclass(slots=True)
class ArtistItem:
    uri: str
    profile: ArtistProfile | None = None


@dataclass(slots=True)
class Artists:
    items: list[ArtistItem] = field(default_factory=list[ArtistItem])


@dataclass(slots=True)
class AudioAssociations:
    total_count: int | None = None


@dataclass(slots=True)
class VideoAssociations:
    total_count: int | None = None


@dataclass(slots=True)
class AssociationsV3:
    audio_associations: AudioAssociations | None = None
    video_associations: VideoAssociations | None = None


@dataclass(slots=True)
class ContentRating:
    label: str | None = None


@dataclass(slots=True)
class Duration:
    total_milliseconds: int


@dataclass(slots=True)
class Playability:
    playable: bool | None = None
    reason: str | None = None


@dataclass(slots=True)
class Track:
    """A search hit with stable identity and optional display metadata.

    Spotify can omit artwork, ratings, album information, and other
    presentation fields. Only track identity and title are required.

    Attributes:
        id: Spotify track ID.
        name: Track title.
        uri: Full Spotify track URI.
        artists: Credited artists, when supplied.
        duration: Track length, when supplied.
    """

    id: str
    name: str
    uri: str
    album_of_track: AlbumOfTrack | None = None
    artists: Artists | None = None
    associations_v3: AssociationsV3 | None = None
    content_rating: ContentRating | None = None
    duration: Duration | None = None
    track_media_type: str | None = None
    playability: Playability | None = None
    visual_identity: VisualIdentity | None = None

    def __repr__(self) -> str:
        items = self.artists.items if self.artists else ()
        names = ", ".join(artist.profile.name for artist in items if artist.profile is not None)

        return f"<Track id={self.id!r} name={self.name!r} artists={names!r}>"
