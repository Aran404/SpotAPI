"""Typed playlist results from Spotify search."""

from __future__ import annotations

from dataclasses import dataclass, field

from .common import (
    ExtractedColors,
    Sources,
    VisualIdentity,
)

__all__ = ("Playlist",)


@dataclass(slots=True)
class PlaylistAttribute:
    key: str
    value: str


@dataclass(slots=True)
class ImageItem:
    extracted_colors: ExtractedColors | None = None
    sources: list[Sources] = field(default_factory=list[Sources])


@dataclass(slots=True)
class Images:
    items: list[ImageItem] = field(default_factory=list[ImageItem])


@dataclass(slots=True)
class OwnerAvatar:
    sources: list[Sources] = field(default_factory=list[Sources])


@dataclass(slots=True)
class OwnerData:
    name: str | None = None
    uri: str | None = None
    username: str | None = None
    avatar: OwnerAvatar | None = None
    _typename: str | None = None


@dataclass(slots=True)
class OwnerV2:
    data: OwnerData | None = None
    _typename: str | None = None


@dataclass(slots=True)
class Playlist:
    """A playlist search hit with optional artwork and owner information.

    Attributes:
        name: Playlist title.
        uri: Full Spotify playlist URI.
        owner_v2: Owner metadata, which may be unavailable or private.
        images: Optional cover images.
    """

    name: str
    uri: str
    attributes: list[PlaylistAttribute] = field(default_factory=list[PlaylistAttribute])
    description: str | None = None
    format: str | None = None
    images: Images | None = None
    owner_v2: OwnerV2 | None = None
    visual_identity: VisualIdentity | None = None

    def __repr__(self) -> str:
        owner = self.owner_v2.data if self.owner_v2 else None

        return (
            f"<Playlist name={self.name!r} "
            f"owner={owner.name if owner else None!r} uri={self.uri!r}>"
        )
