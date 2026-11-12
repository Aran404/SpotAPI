"""Affinity ranking windows and typed top-content pages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypeAlias

from spotapi.models.catalogue import Artist, Track

TimeRange: TypeAlias = Literal["short_term", "medium_term", "long_term"]


@dataclass(frozen=True, slots=True)
class TopContent:
    """A page of Spotify affinity rankings for artists and tracks.

    The totals belong to the requested rankings. They do not represent exact
    listening counts or a complete playback history.
    """

    artists: tuple[Artist, ...]
    tracks: tuple[Track, ...]
    total_artists: int
    total_tracks: int
