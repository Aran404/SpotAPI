"""Typed artist overview returned by ``queryArtistOverview``.

Only stable, useful fields are modeled; variable Spotify experiment payloads
are deliberately left as optional opaque data rather than guessed schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .common import ExtractedColorSet, Sources
from .track import Duration
from .track_details import SharingInfo

__all__ = ("ArtistDetails",)


@dataclass(slots=True)
class ArtistCity:
    city: str
    country: str
    number_of_listeners: int
    region: str | None = None


@dataclass(slots=True)
class ArtistCities:
    items: list[ArtistCity] = field(default_factory=list[ArtistCity])


@dataclass(slots=True)
class ArtistStats:
    followers: int
    monthly_listeners: int
    world_rank: int | None = None
    top_cities: ArtistCities | None = None


@dataclass(slots=True)
class ArtistBiography:
    text: str
    type: str | None = None


@dataclass(slots=True)
class ArtistPinnedItem:
    title: str
    uri: str
    subtitle: str | None = None
    comment: str | None = None
    type: str | None = None


@dataclass(slots=True)
class ArtistProfileDetails:
    name: str
    biography: ArtistBiography | None = None
    pinned_item: ArtistPinnedItem | None = None


@dataclass(slots=True)
class ArtistReleaseDate:
    year: int
    month: int | None = None
    day: int | None = None
    precision: str | None = None


@dataclass(slots=True)
class ArtistArtwork:
    sources: list[Sources] = field(default_factory=list[Sources])


@dataclass(slots=True)
class ArtistRelease:
    name: str
    uri: str
    id: str | None = None
    type: str | None = None
    date: ArtistReleaseDate | None = None
    cover_art: ArtistArtwork | None = None
    label: str | None = None
    sharing_info: SharingInfo | None = None


@dataclass(slots=True)
class ArtistReleaseList:
    items: list[ArtistRelease] = field(default_factory=list[ArtistRelease])
    total_count: int | None = None


@dataclass(slots=True)
class ArtistReleaseGroup:
    releases: ArtistReleaseList


@dataclass(slots=True)
class ArtistReleaseGroups:
    items: list[ArtistReleaseGroup] = field(default_factory=list[ArtistReleaseGroup])
    total_count: int | None = None


@dataclass(slots=True)
class ArtistTopTrack:
    name: str
    uri: str
    playcount: str | None = None
    duration: Duration | None = None


@dataclass(slots=True)
class ArtistTopTrackItem:
    track: ArtistTopTrack
    uid: str | None = None


@dataclass(slots=True)
class ArtistTopTracks:
    items: list[ArtistTopTrackItem] = field(default_factory=list[ArtistTopTrackItem])


@dataclass(slots=True)
class ArtistDiscographyDetails:
    albums: ArtistReleaseGroups | None = None
    singles: ArtistReleaseGroups | None = None
    compilations: ArtistReleaseGroups | None = None
    latest: ArtistRelease | None = None
    popular_releases_albums: ArtistReleaseList | None = None
    top_tracks: ArtistTopTracks | None = None


@dataclass(slots=True)
class ArtistRelatedArtist:
    uri: str
    profile: ArtistProfileDetails
    id: str | None = None

    @property
    def name(self) -> str:
        """Return the display name from the resource's profile metadata."""
        return self.profile.name


@dataclass(slots=True)
class ArtistRelatedArtists:
    items: list[ArtistRelatedArtist] = field(default_factory=list[ArtistRelatedArtist])
    total_count: int | None = None


@dataclass(slots=True)
class ArtistRelatedContent:
    related_artists: ArtistRelatedArtists | None = None


@dataclass(slots=True)
class ArtistVerification:
    is_verified: bool
    is_registered: bool | None = None


@dataclass(slots=True)
class ArtistReputation:
    verification: ArtistVerification


@dataclass(slots=True)
class ArtistAvatar:
    sources: list[Sources] = field(default_factory=list[Sources])


@dataclass(slots=True)
class ArtistVisuals:
    avatar_image: ArtistAvatar | None = None


@dataclass(slots=True)
class ArtistWideImage:
    extracted_color_set: ExtractedColorSet | None = None


@dataclass(slots=True)
class ArtistVisualIdentity:
    wide_full_bleed_image: ArtistWideImage | None = None


@dataclass(slots=True)
class ArtistDetails:
    """Full artist overview, with convenient typed popularity and catalog data."""

    id: str
    uri: str
    profile: ArtistProfileDetails
    stats: ArtistStats | None = None
    discography: ArtistDiscographyDetails | None = None
    related_content: ArtistRelatedContent | None = None
    on_platform_reputation_trait: ArtistReputation | None = None
    visuals: ArtistVisuals | None = None
    visual_identity: ArtistVisualIdentity | None = None
    sharing_info: SharingInfo | None = None
    saved: bool | None = None

    @property
    def name(self) -> str:
        """Artist display name from the nested Spotify profile."""
        return self.profile.name
