"""Typed album results from Spotify search."""

from __future__ import annotations

from dataclasses import dataclass, field

from .common import CoverArt, VisualIdentity

__all__ = ("Album",)


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
class Date:
    year: int


@dataclass(slots=True)
class Playability:
    playable: bool | None = None
    reason: str | None = None


@dataclass(slots=True)
class Album:
    """An album search hit with optional release and artwork metadata.

    Attributes:
        name: Display title.
        uri: Full Spotify album URI.
        artists: Credited artists, when supplied.
        date: Release year, when supplied.
    """

    name: str
    uri: str
    artists: Artists | None = None
    cover_art: CoverArt | None = None
    date: Date | None = None
    is_album_pre_release: bool | None = None
    playability: Playability | None = None
    pre_release_end_date_time: str | None = None
    type: str | None = None
    visual_identity: VisualIdentity | None = None

    @property
    def id(self) -> str:
        """Spotify album ID, derived from the canonical album URI."""
        return self.uri.rsplit(":", 1)[-1]

    def __repr__(self) -> str:
        items = self.artists.items if self.artists else ()
        artists = ", ".join(item.profile.name for item in items if item.profile is not None)
        year = self.date.year if self.date is not None else None

        return f"<Album name={self.name!r} year={year!r} artists={artists!r} uri={self.uri!r}>"
