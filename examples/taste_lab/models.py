"""Small persisted models shared by import, ranking, and observation."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

FeedbackKind = Literal["like", "dislike", "complete", "early_transition", "interrupted", "unsave"]


@dataclass(frozen=True, slots=True)
class Song:
    uri: str
    name: str
    artists: tuple[str, ...]
    artist_names: tuple[str, ...]
    duration_ms: int = 0
    monthly_listeners: int | None = None
    bpm: float | None = None

    def __post_init__(self) -> None:
        if not self.uri.startswith("spotify:track:") or len(self.artists) != len(
            self.artist_names
        ):
            raise ValueError("A song needs a track URI and matching artist IDs/names")
        if self.duration_ms < 0 or (
            self.monthly_listeners is not None and self.monthly_listeners < 0
        ):
            raise ValueError("Duration and audience size must be nonnegative")
        if self.bpm is not None and (not math.isfinite(self.bpm) or self.bpm <= 0):
            raise ValueError("Tempo must be finite and positive when supplied")

    @property
    def url(self) -> str:
        return "https://open.spotify.com/track/" + self.uri.rsplit(":", 1)[-1]


@dataclass(frozen=True, slots=True)
class Seed:
    source: str
    song: Song
    weight: float


@dataclass(frozen=True, slots=True)
class Candidate:
    song: Song
    bridges: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Feedback:
    id: str
    uri: str
    kind: FeedbackKind
    at: float
    confidence: float = 1.0


@dataclass(frozen=True, slots=True)
class Snapshot:
    seeds: tuple[Seed, ...]
    candidates: tuple[Candidate, ...]
    feedback: tuple[Feedback, ...]
    impressions: dict[str, float]
    remembered: tuple[Song, ...] = ()


@dataclass(frozen=True, slots=True)
class Recommendation:
    song: Song
    score: float
    affinity: float
    novelty: float
    reasons: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Benchmark:
    train: tuple[Seed, ...]
    held: tuple[Seed, ...]
    candidates: tuple[Candidate, ...]
