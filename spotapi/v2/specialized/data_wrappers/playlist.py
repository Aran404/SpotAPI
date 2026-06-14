from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from spotapi.v2.specialized.data_wrappers.common import (
    ExtractedColors,
    Sources,
    VisualIdentity,
)

__all__: tuple[str, ...] = ("Playlist",)


@dataclass(slots=True)
class ImageItem:
    extracted_colors: ExtractedColors
    sources: list[Sources]


@dataclass(slots=True)
class Images:
    items: list[ImageItem]


@dataclass(slots=True)
class OwnerAvatar:
    sources: list[Sources]


@dataclass(slots=True)
class OwnerData:
    _typename: str
    avatar: OwnerAvatar
    name: str
    uri: str
    username: str


@dataclass(slots=True)
class OwnerV2:
    _typename: str
    data: OwnerData


@dataclass(slots=True)
class Playlist:
    """A Spotify playlist returned by the search API.

    Attributes
    ----------
    name : str
        Display name of the playlist.
    uri : str
        Spotify URI (``spotify:playlist:<id>``).
    description : str
        User-provided playlist description (may be empty).
    format : str
        Internal format string (e.g. ``"default"``).
    owner_v2 : OwnerV2
        The playlist owner's profile data.
    images : Images
        Cover image sources with extracted color data.
    visual_identity : VisualIdentity
        Theme color set derived from the cover image.
    attributes : list
        Arbitrary Spotify-side attribute list (usually empty).
    """

    attributes: list[Any]
    description: str
    format: str
    images: Images
    name: str
    owner_v2: OwnerV2
    uri: str
    visual_identity: VisualIdentity

    def __repr__(self) -> str:
        owner = self.owner_v2.data.name
        return f"<Playlist name={self.name!r}" f" owner={owner!r}" f" uri={self.uri!r}>"
