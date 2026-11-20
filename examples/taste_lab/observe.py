"""Infer weak listening signals from contiguous playback observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from uuid import uuid4

from .models import Feedback, FeedbackKind


@dataclass(frozen=True, slots=True)
class Sample:
    uri: str
    occurrence: str | None
    device: str
    position_ms: int
    duration_ms: int
    playing: bool


class Observer:
    """Credit observed intervals only; interruptions never count as skips."""

    def __init__(self) -> None:
        self.previous: Sample | None = None
        self.clock: float | None = None
        self.heard = 0.0
        self.ambiguous = False
        self.session_id = ""

    def _begin(self, sample: Sample | None, clock: float) -> None:
        self.previous = sample
        self.clock = clock
        self.heard = 0
        self.ambiguous = False
        self.session_id = str(uuid4())

    def finish(self, at: float, *, transition: bool = False) -> Feedback | None:
        previous = self.previous
        if previous is None or self.heard < 5 or previous.duration_ms <= 0:
            return None

        coverage = min(1.0, self.heard * 1000 / previous.duration_ms)
        kind: FeedbackKind = "interrupted"
        confidence = coverage
        if transition and not self.ambiguous and previous.playing:
            if coverage >= 0.8 and previous.position_ms >= 0.9 * previous.duration_ms:
                kind, confidence = "complete", 1.0
            elif coverage < 0.5 and previous.position_ms < 0.75 * previous.duration_ms:
                kind, confidence = "early_transition", 0.25

        return Feedback(self.session_id, previous.uri, kind, at, confidence)

    def observe(self, sample: Sample | None, *, clock: float, at: float) -> Feedback | None:
        if not math.isfinite(clock) or not math.isfinite(at):
            raise ValueError("Observation clocks must be finite")

        previous, previous_clock = self.previous, self.clock
        if previous is None or previous_clock is None:
            self._begin(sample, clock)
            return None

        elapsed = clock - previous_clock
        if sample is None or elapsed <= 0 or elapsed > 3 or sample.device != previous.device:
            event = self.finish(at)
            self._begin(sample, clock)
            return event

        changed = (sample.uri, sample.occurrence) != (previous.uri, previous.occurrence)
        repeated = (
            sample.position_ms < previous.position_ms
            and previous.position_ms >= 0.9 * previous.duration_ms
            and sample.position_ms <= 0.1 * previous.duration_ms
        )
        if changed or repeated:
            event = self.finish(at, transition=changed and sample.uri != previous.uri or repeated)
            self._begin(sample, clock)
            return event

        progress = (sample.position_ms - previous.position_ms) / 1000
        if not 0 <= progress <= elapsed + 0.75:
            self.ambiguous = True
        elif previous.playing and sample.playing:
            self.heard += min(progress, elapsed)

        self.previous, self.clock = sample, clock
        return None
