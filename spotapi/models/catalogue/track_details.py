"""Models for individual track lookups."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import (
    VisualIdentity,
)
from .track import (
    ArtistProfile,
    ContentRating,
    CoverArt,
    Duration,
    Playability,
)

__all__ = ("TrackDetails",)


@dataclass(slots=True)
class SharingInfo:
    share_id: str | None = None
    share_url: str | None = None


@dataclass(slots=True)
class ReleaseDate:
    iso_string: str
    precision: str | None = None
    year: int | None = None


@dataclass(slots=True)
class CopyrightItem:
    text: str
    type: str


@dataclass(slots=True)
class Copyright:
    items: list[CopyrightItem] = field(default_factory=list[CopyrightItem])
    total_count: int | None = None


@dataclass(slots=True)
class AlbumPlayability:
    playable: bool | None = None


@dataclass(slots=True)
class AlbumTrack:
    uri: str
    track_number: int | None = None


@dataclass(slots=True)
class AlbumTrackItem:
    track: AlbumTrack | None = None


@dataclass(slots=True)
class AlbumTracks:
    items: list[AlbumTrackItem] = field(default_factory=list[AlbumTrackItem])
    total_count: int | None = None


@dataclass(slots=True)
class AlbumOfTrack:
    id: str
    name: str
    uri: str
    cover_art: CoverArt | None = None
    copyright: Copyright | None = None
    courtesy_line: str | None = None
    date: ReleaseDate | None = None
    playability: AlbumPlayability | None = None
    sharing_info: SharingInfo | None = None
    tracks: AlbumTracks | None = None
    type: str | None = None


@dataclass(slots=True)
class AudioAssociations:
    items: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])


@dataclass(slots=True)
class VideoAssociations:
    total_count: int | None = None


@dataclass(slots=True)
class AssociationsV3:
    audio_associations: AudioAssociations | None = None
    video_associations: VideoAssociations | None = None


@dataclass(slots=True)
class ArtistImageSource:
    url: str
    height: int | None = None
    width: int | None = None


@dataclass(slots=True)
class ArtistAvatarImage:
    sources: list[ArtistImageSource] = field(default_factory=list[ArtistImageSource])


@dataclass(slots=True)
class ArtistVisuals:
    avatar_image: ArtistAvatarImage | None = None


@dataclass(slots=True)
class ArtistItem:
    uri: str
    id: str | None = None
    profile: ArtistProfile | None = None
    visuals: ArtistVisuals | None = None


@dataclass(slots=True)
class ArtistCollection:
    items: list[ArtistItem] = field(default_factory=list[ArtistItem])
    total_count: int | None = None


@dataclass(slots=True)
class RelatedContent:
    related_artists: ArtistCollection | None = None


@dataclass(slots=True)
class ArtistDiscography:
    albums: dict[str, Any] | None = None
    popular_releases_albums: dict[str, Any] | None = None
    singles: dict[str, Any] | None = None
    top_tracks: dict[str, Any] | None = None


@dataclass(slots=True)
class FirstArtistItem(ArtistItem):
    discography: ArtistDiscography | None = None
    related_content: RelatedContent | None = None


@dataclass(slots=True)
class FirstArtistGroup:
    items: list[FirstArtistItem] = field(default_factory=list[FirstArtistItem])
    total_count: int | None = None


@dataclass(slots=True)
class ArtistGroup:
    items: list[ArtistItem] = field(default_factory=list[ArtistItem])
    total_count: int | None = None


@dataclass(slots=True)
class TrackDetails:
    """Track lookup including play count and optional rich metadata.

    Attributes:
        duration: Total track duration.
        id: Spotify track ID.
        name: Track title.
        playcount: Spotify's string-formatted play count.
        uri: Full Spotify track URI.
        album_of_track: Album information, when supplied.
        first_artist: Primary artist and discography, when available.
        other_artists: Additional credited artists, when available.
    """

    duration: Duration
    id: str
    name: str
    playcount: str
    uri: str
    album_of_track: AlbumOfTrack | None = None
    associations_v3: AssociationsV3 | None = None
    content_rating: ContentRating | None = None
    content_rating_v2: dict[str, Any] | None = None
    media_type: str | None = None
    playability: Playability | None = None
    saved: bool | None = None
    sharing_info: SharingInfo | None = None
    track_number: int | None = None
    visual_identity: VisualIdentity | None = None
    first_artist: FirstArtistGroup | None = None
    other_artists: ArtistGroup | None = None

    def __repr__(self) -> str:
        artist_name: str | None = None

        if self.first_artist and self.first_artist.items:
            profile = self.first_artist.items[0].profile

            if profile is not None:
                artist_name = profile.name

        artist = f" artist={artist_name!r}" if artist_name is not None else ""

        return f"<TrackDetails id={self.id!r} name={self.name!r}{artist}>"
