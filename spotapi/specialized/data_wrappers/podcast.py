"""Typed podcast search results and compatible episode export."""

from __future__ import annotations

from dataclasses import dataclass, field

from .common import (
    CoverArt,
    VisualIdentity,
)
from .podcast_episode import PodcastEpisodeDetails

__all__ = ("Podcast", "PodcastEpisodeDetails")


@dataclass(slots=True)
class Publisher:
    name: str | None = None


@dataclass(slots=True)
class TopicItem:
    uri: str
    title: str | None = None
    _typename: str | None = None


@dataclass(slots=True)
class Topics:
    items: list[TopicItem] = field(default_factory=list[TopicItem])


@dataclass(slots=True)
class Podcast:
    """A podcast search hit with optional artwork, publisher, and topics.

    Attributes:
        name: Podcast title.
        uri: Full Spotify show URI.
        publisher: Optional publisher metadata.
    """

    name: str
    uri: str
    _typename: str | None = None
    cover_art: CoverArt | None = None
    media_type: str | None = None
    publisher: Publisher | None = None
    topics: Topics | None = None
    visual_identity: VisualIdentity | None = None

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        publisher = self.publisher.name if self.publisher else None

        return f"<Podcast name={self.name!r} publisher={publisher!r} uri={self.uri!r}>"
