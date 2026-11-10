"""Models for individual album lookups."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .album import (
    ArtistItem,
    Artists,
    CoverArt,
    Date,
)
from .album import (
    Playability as AlbumPlayability,
)
from .common import (
    Sources,
    VisualIdentity,
)
from .track import (
    ContentRating,
    Duration,
)
from .track import (
    Playability as TrackPlayability,
)
from .track_details import (
    ArtistVisuals,
    Copyright,
    SharingInfo,
)

__all__ = ("AlbumDetails",)


@dataclass(slots=True)
class ReleaseDate:
    iso_string: str
    precision: str | None = None

    @property
    def year(self) -> int:
        """Return the available release year without inventing an unknown date."""
        return int(self.iso_string[:4])


@dataclass(slots=True)
class ArtistSharingInfo:
    share_url: str | None = None


@dataclass(slots=True)
class AlbumArtist(ArtistItem):
    id: str | None = None
    sharing_info: ArtistSharingInfo | None = None
    visuals: ArtistVisuals | None = None


@dataclass(slots=True)
class AssociationCount:
    total_count: int | None = None


@dataclass(slots=True)
class TrackAssociations:
    audio_associations: AssociationCount | None = None
    video_associations: AssociationCount | None = None


@dataclass(slots=True)
class AlbumTrack:
    """Track metadata embedded in an album details response."""

    name: str
    uri: str
    artists: Artists | None = None
    associations_v3: TrackAssociations | None = None
    content_rating: ContentRating | None = None
    disc_number: int | None = None
    duration: Duration | None = None
    media_type: str | None = None
    playability: TrackPlayability | None = None
    playcount: str | None = None
    saved: bool | None = None
    track_number: int | None = None
    relinking_information: dict[str, Any] | None = None

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]


@dataclass(slots=True)
class AlbumTrackItem:
    track: AlbumTrack | None = None
    uid: str | None = None


@dataclass(slots=True)
class AlbumTracks:
    items: list[AlbumTrackItem] = field(default_factory=list[AlbumTrackItem])
    total_count: int | None = None


@dataclass(slots=True)
class AlbumArtists:
    items: list[AlbumArtist] = field(default_factory=list[AlbumArtist])
    total_count: int | None = None


@dataclass(slots=True)
class Disc:
    number: int
    tracks: AssociationCount | None = None


@dataclass(slots=True)
class AlbumDiscs:
    items: list[Disc] = field(default_factory=list[Disc])
    total_count: int | None = None


@dataclass(slots=True)
class RelatedCoverArt:
    """Related releases omit extracted colors."""

    sources: list[Sources] = field(default_factory=list[Sources])


@dataclass(slots=True)
class RelatedAlbum:
    name: str
    uri: str
    cover_art: RelatedCoverArt | None = None
    date: Date | None = None
    id: str | None = None
    playability: AlbumPlayability | None = None
    sharing_info: SharingInfo | None = None
    type: str | None = None


@dataclass(slots=True)
class RelatedAlbums:
    items: list[RelatedAlbum] = field(default_factory=list[RelatedAlbum])
    total_count: int | None = None


@dataclass(slots=True)
class ArtistDiscography:
    popular_releases_albums: RelatedAlbums | None = None


@dataclass(slots=True)
class MoreAlbumsByArtistItem:
    discography: ArtistDiscography | None = None


@dataclass(slots=True)
class MoreAlbumsByArtist:
    items: list[MoreAlbumsByArtistItem] = field(default_factory=list[MoreAlbumsByArtistItem])
    total_count: int | None = None


@dataclass(slots=True)
class AlbumReleases:
    items: list[dict[str, Any]] = field(default_factory=list[dict[str, Any]])
    total_count: int | None = None


@dataclass(slots=True)
class AlbumDetails:
    """Album lookup including optional tracks, artists, and related releases.

    Attributes:
        date: Album release date.
        name: Album title.
        uri: Full Spotify album URI.
        artists: Credited artists, when available.
        tracks_v2: Track collection, when provided by Spotify.
        discs: Disc information, when available.
        more_albums_by_artist: Additional artist releases, if supplied.
    """

    date: ReleaseDate
    name: str
    uri: str
    artists: AlbumArtists | None = None
    copyright: Copyright | None = None
    courtesy_line: str | None = None
    cover_art: CoverArt | None = None
    discs: AlbumDiscs | None = None
    is_pre_release: bool | None = None
    label: str | None = None
    playability: AlbumPlayability | None = None
    saved: bool | None = None
    sharing_info: SharingInfo | None = None
    tracks_v2: AlbumTracks | None = None
    type: str | None = None
    visual_identity: VisualIdentity | None = None
    more_albums_by_artist: MoreAlbumsByArtist | None = None
    pre_release_end_date_time: str | None = None
    releases: AlbumReleases | None = None
    watch_feed_entrypoint: dict[str, Any] | None = None

    @property
    def id(self) -> str:
        """Spotify album ID, derived from its URI."""
        return self.uri.rsplit(":", 1)[-1]

    @property
    def tracks(self) -> list[AlbumTrack]:
        """Track objects without the GraphQL item wrappers."""
        return [
            item.track
            for item in (self.tracks_v2.items if self.tracks_v2 else ())
            if item.track is not None
        ]

    @property
    def more_albums(self) -> list[RelatedAlbum]:
        """Related releases without the discography wrappers."""
        if self.more_albums_by_artist is None:
            return []

        albums: list[RelatedAlbum] = []

        for item in self.more_albums_by_artist.items:
            discography = item.discography
            releases = discography.popular_releases_albums if discography else None

            if releases is not None:
                albums.extend(releases.items)

        return albums

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return (
            f"<AlbumDetails id={self.id!r} name={self.name!r} "
            f"tracks={self.tracks_v2.total_count if self.tracks_v2 else None!r}>"
        )
