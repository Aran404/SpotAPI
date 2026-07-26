from __future__ import annotations

from dataclasses import dataclass

from spotapi.v2.specialized.data_wrappers.common import (
    ExtractedColors,
    Sources,
    VisualIdentity,
)

__all__: tuple[str, ...] = ("Podcast",)


@dataclass(slots=True)
class CoverArt:
    extracted_colors: ExtractedColors
    sources: list[Sources]


@dataclass(slots=True)
class Publisher:
    name: str


@dataclass(slots=True)
class TopicItem:
    _typename: str
    title: str
    uri: str


@dataclass(slots=True)
class Topics:
    items: list[TopicItem]


@dataclass(slots=True)
class Podcast:
    """A Spotify podcast (show) returned by the search API.

    Attributes
    ----------
    name : str
        Podcast display title.
    uri : str
        Spotify URI (``spotify:show:<id>``).
    media_type : str
        ``"AUDIO"`` or ``"VIDEO"``.
    publisher : Publisher
        The publisher / creator name.
    topics : Topics
        Associated topic tags.
    cover_art : CoverArt
        Cover image sources and extracted colors.
    visual_identity : VisualIdentity
        Theme color set derived from the cover image.
    _typename : str
        Spotify's internal GraphQL ``__typename`` discriminator.
    """

    _typename: str
    cover_art: CoverArt
    media_type: str
    name: str
    publisher: Publisher
    topics: Topics
    uri: str
    visual_identity: VisualIdentity

    def __repr__(self) -> str:
        return (
            f"<Podcast name={self.name!r}"
            f" publisher={self.publisher.name!r}"
            f" uri={self.uri!r}>"
        )
