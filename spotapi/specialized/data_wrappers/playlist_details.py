"""Public playlist metadata, occurrences, and optional DJ metadata."""

from __future__ import annotations

from dataclasses import dataclass

from .catalogue import Episode
from .playlist import Playlist
from .playlist_track import PlaylistTrack

__all__ = ("PlaylistDetails", "PlaylistEntry")


@dataclass(slots=True)
class PlaylistCount:
    total_count: int | None = None


@dataclass(slots=True)
class PlaylistDetails(Playlist):
    followers: int | None = None
    revision_id: str | None = None
    content: PlaylistCount | None = None

    @property
    def total_count(self) -> int | None:
        """Return the supplied playlist count, or None when it is unavailable."""
        return self.content.total_count if self.content else None

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<PlaylistDetails name={self.name!r} items={self.total_count!r}>"


@dataclass(slots=True)
class PlaylistEntry:
    """One occurrence; unavailable content keeps its place with item=None."""

    item: PlaylistTrack | Episode | None
    uid: str | None = None
    added_at: str | None = None

    @property
    def uri(self) -> str | None:
        """Return the available occurrence's URI, or None for unavailable content."""
        return self.item.uri if self.item else None
