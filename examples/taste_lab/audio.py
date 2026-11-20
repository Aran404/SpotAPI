"""Versioned audio representations and a conservative, local kernel preference model.

Embeddings describe sound, not enjoyment or neurological complexity. Missing audio
provides no evidence. No audio files or personal feedback leave this application.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, cast

from .models import Seed

Vector = tuple[float, ...]


def unit(values: Sequence[float]) -> Vector:
    if not values or not all(math.isfinite(value) for value in values):
        raise ValueError("An embedding needs finite, nonempty coordinates")

    length = math.hypot(*values)
    if not math.isfinite(length) or length <= 1e-12:
        raise ValueError("An embedding must have a nonzero finite length")

    return tuple(value / length for value in values)


def cosine(left: Vector, right: Vector) -> float:
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right, strict=True))))


def _nearest_function(references: tuple[Vector, ...]) -> Callable[[Vector], list[float]]:
    """Build the index once. BLAS avoids Python loops across large audio libraries."""
    if len(references) > 32:
        try:
            np: Any = importlib.import_module("numpy")
        except ImportError:
            pass
        else:
            matrix = np.asarray(references, dtype="float32")

            def accelerated(vector: Vector) -> list[float]:
                similarities = np.clip(matrix @ np.asarray(vector, dtype="float32"), -1, 1)
                count = min(3, len(references))
                nearest = np.partition(similarities, len(references) - count)[-count:]
                return sorted(cast(list[float], nearest.tolist()), reverse=True)

            return accelerated

    def ordinary(vector: Vector) -> list[float]:
        return sorted((cosine(vector, reference) for reference in references), reverse=True)[:3]

    return ordinary


@dataclass(frozen=True, slots=True)
class AudioFeatures:
    uri: str
    model: str
    digest: str
    sections: tuple[Vector, ...]
    source_url: str = ""
    offset_ms: int = 0

    def __post_init__(self) -> None:
        if not self.uri.startswith("spotify:track:") or not self.model or not self.digest:
            raise ValueError("Audio features need a track, model identity and source digest")

        if not self.sections or len({len(section) for section in self.sections}) != 1:
            raise ValueError("Audio sections must have consistent, nonempty dimensions")

        object.__setattr__(self, "sections", tuple(unit(section) for section in self.sections))

    @property
    def center(self) -> Vector:
        coordinates = tuple(sum(column) for column in zip(*self.sections, strict=True))
        # Opposing sections can cancel; preserve a real section rather than inventing a direction.
        return unit(coordinates) if math.hypot(*coordinates) > 1e-12 else self.sections[0]


@dataclass(frozen=True, slots=True)
class AudioMatch:
    affinity: float
    preference: float
    neighbors: int


class AudioTaste:
    """Keep separate library examples instead of collapsing distinct musical tastes.

    Nearest-example affinity supports cold start. Kernel-weighted feedback adjusts
    neighboring sounds, shrunk toward zero until evidence accumulates. Cosine
    similarity is a ranking feature, never a calibrated probability of enjoyment.
    """

    def __init__(
        self,
        features: Sequence[AudioFeatures],
        seeds: tuple[Seed, ...],
        feedback: dict[str, tuple[float, float]],
    ) -> None:
        identities = {(item.model, len(item.sections[0])) for item in features}
        if len(identities) > 1:
            raise ValueError("Cannot compare different audio models or dimensions")

        self.vectors = {item.uri: item.center for item in features}
        # Repeated membership in playlists must not duplicate one recording's evidence.
        self.anchors = {seed.song.uri for seed in seeds}.intersection(self.vectors)
        self.feedback = {uri: counts for uri, counts in feedback.items() if uri in self.vectors}
        self._nearest = _nearest_function(tuple(self.vectors[uri] for uri in sorted(self.anchors)))

    def match(self, uri: str) -> AudioMatch | None:
        vector = self.vectors.get(uri)
        if vector is None or not self.anchors:
            return None

        if uri in self.anchors:
            # Evaluation callers may query an anchor; it must not match itself.
            similarities = sorted(
                (cosine(vector, self.vectors[anchor]) for anchor in self.anchors if anchor != uri),
                reverse=True,
            )[:3]
        else:
            similarities = self._nearest(vector)
        if not similarities:
            return None

        # A single strong neighbor preserves small taste clusters. Other neighbors stabilize it.
        affinity = max(0.0, 0.7 * similarities[0] + 0.3 * sum(similarities) / len(similarities))
        numerator, denominator = 0.0, 4.0
        for neighbor, (positive, negative) in self.feedback.items():
            if neighbor == uri:
                continue

            similarity = max(0.0, cosine(vector, self.vectors[neighbor])) ** 8
            numerator += similarity * (positive - negative)
            denominator += similarity * (positive + negative)

        return AudioMatch(affinity, numerator / denominator, len(similarities))
