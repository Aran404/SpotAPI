"""Artist-disjoint retrospective checks without inventing disliked tracks."""

from __future__ import annotations

import random
from dataclasses import dataclass

from .audio import AudioFeatures
from .engine import Policy, audio_taste, recommend
from .models import Candidate, Seed, Snapshot


@dataclass(frozen=True, slots=True)
class Evaluation:
    training_tracks: int
    withheld_tracks: int
    retrieved_tracks: int
    candidate_tracks: int
    cutoff: int
    model_hits: int
    popularity_hits: int
    random_mean_hits: float
    audio_hits: int | None
    audio_training_tracks: int
    audio_candidate_tracks: int

    @property
    def retrieval_recall(self) -> float | None:
        return self.retrieved_tracks / self.withheld_tracks if self.withheld_tracks else None

    @property
    def ranking_recall(self) -> float | None:
        return self.model_hits / self.retrieved_tracks if self.retrieved_tracks else None


def compare(
    train: tuple[Seed, ...],
    held: tuple[Seed, ...],
    candidates: tuple[Candidate, ...],
    *,
    cutoff: int = 10,
    features: tuple[AudioFeatures, ...] = (),
) -> Evaluation:
    """Measure recovery of withheld library positives; all other tracks are unlabeled."""
    training = {seed.song.uri for seed in train}
    positives = {seed.song.uri for seed in held}
    if training.intersection(positives):
        raise ValueError("Evaluation partitions share track identities")

    artists = {artist for seed in train for artist in seed.song.artists}
    if artists.intersection(artist for seed in held for artist in seed.song.artists):
        raise ValueError("Evaluation partitions share artists")

    pool = {
        candidate.song.uri: candidate
        for candidate in candidates
        if candidate.song.uri not in training
    }
    retrieved = positives.intersection(pool)
    snapshot = Snapshot(train, tuple(pool.values()), (), {})
    ranked = recommend(snapshot, now=0, limit=cutoff, policy=Policy(cooldown_hours=0))
    model_hits = sum(item.song.uri in positives for item in ranked)
    audio_hits = None
    audio_uris = {item.uri for item in features}
    if features and training.intersection(audio_uris) and pool.keys() & audio_uris:
        audio_ranked = recommend(
            snapshot,
            now=0,
            limit=cutoff,
            policy=Policy(cooldown_hours=0),
            audio=audio_taste(snapshot, features, 0),
        )
        audio_hits = sum(item.song.uri in positives for item in audio_ranked)
    popularity = sorted(
        pool.values(),
        key=lambda item: (-(item.song.monthly_listeners or 0), item.song.uri),
    )
    popularity_hits = sum(item.song.uri in positives for item in popularity[:cutoff])
    randomizer = random.Random(7)
    values = sorted(pool)
    random_hits = [
        sum(uri in positives for uri in randomizer.sample(values, min(cutoff, len(values))))
        for _ in range(100)
    ]

    return Evaluation(
        len(training),
        len(positives),
        len(retrieved),
        len(pool),
        cutoff,
        model_hits,
        popularity_hits,
        sum(random_hits) / len(random_hits),
        audio_hits,
        len(training.intersection(audio_uris)),
        len(pool.keys() & audio_uris),
    )
