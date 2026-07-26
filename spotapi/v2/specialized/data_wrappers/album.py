from __future__ import annotations

from dataclasses import dataclass

from spotapi.v2.specialized.data_wrappers.common import (
    ExtractedColors,
    Sources,
    VisualIdentity,
)

__all__: tuple[str, ...] = ("Album",)


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
class CoverArt:
    extracted_colors: ExtractedColors
    sources: list[Sources]


@dataclass(slots=True)
class Date:
    year: int


@dataclass(slots=True)
class Playability:
    playable: bool
    reason: str


@dataclass(slots=True)
class Album:
    """A Spotify album returned by the search API.

    Attributes
    ----------
    name : str
        Album title.
    uri : str
        Spotify URI (``spotify:album:<id>``).
    type : str
        ``"ALBUM"``, ``"SINGLE"``, or ``"COMPILATION"``.
    date : Date
        Release year.
    artists : Artists
        Credited artists.
    cover_art : CoverArt
        Cover image sources and extracted colors.
    playability : Playability
        Whether the album is playable in the current market.
    is_album_pre_release : bool
        ``True`` if the album has not yet been officially released.
    pre_release_end_date_time : str, optional
        ISO-8601 timestamp marking the end of the pre-release window.
    visual_identity : VisualIdentity
        Theme color set extracted from the cover art.
    """

    artists: Artists
    cover_art: CoverArt
    date: Date
    is_album_pre_release: bool
    name: str
    playability: Playability
    type: str
    uri: str
    visual_identity: VisualIdentity
    pre_release_end_date_time: str | None = None

    def __repr__(self) -> str:
        artist_names = ", ".join(a.profile.name for a in (self.artists.items or []))
        return (
            f"<Album name={self.name!r}"
            f" year={self.date.year}"
            f" artists={artist_names!r}"
            f" uri={self.uri!r}>"
        )
