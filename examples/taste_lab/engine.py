"""Explainable ranking with contextual affinity and conservative online feedback."""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass, field

from .audio import AudioFeatures, AudioTaste
from .models import Candidate, Feedback, Recommendation, Seed, Snapshot, Song

DAY = 86_400


@dataclass(frozen=True, slots=True)
class Policy:
    novelty: float = 0.45
    cooldown_hours: float = 48
    smaller_artist_listeners: int = 250_000

    def __post_init__(self) -> None:
        if not math.isfinite(self.novelty) or not 0 <= self.novelty <= 1:
            raise ValueError("Novelty must be between 0 and 1")
        if not math.isfinite(self.cooldown_hours) or self.cooldown_hours < 0:
            raise ValueError("Cooldown must be finite and nonnegative")
        if self.smaller_artist_listeners < 1:
            raise ValueError("The listener threshold must be positive")


@dataclass(slots=True)
class Evidence:
    positive: float = 0
    negative: float = 0
    listens: int = 0
    last_listened: float = -math.inf
    blocked: bool = False
    saved: bool = False

    @property
    def mean(self) -> float:
        return (2 + self.positive) / (4 + self.positive + self.negative)

    @property
    def uncertainty(self) -> float:
        a, b = 2 + self.positive, 2 + self.negative
        return math.sqrt(a * b / ((a + b) ** 2 * (a + b + 1)))


def evidence(events: tuple[Feedback, ...], now: float) -> dict[str, Evidence]:
    result: dict[str, Evidence] = defaultdict(Evidence)
    for event in sorted(events, key=lambda item: (item.at, item.id)):
        if event.at > now:
            continue

        item = result[event.uri]
        weight = event.confidence * math.exp(-max(0, now - event.at) / (90 * DAY))
        if event.kind == "like":
            item.positive += 3 * weight
            item.saved, item.blocked = True, False
        elif event.kind == "dislike":
            item.negative += 4 * weight
            item.blocked = True
        elif event.kind == "complete":
            item.positive += 0.2 * weight
            item.listens += 1
            item.last_listened = event.at
        elif event.kind == "early_transition":
            item.negative += 0.15 * weight
            item.listens += 1
            item.last_listened = event.at
        elif event.kind == "unsave":
            item.saved = False
        elif event.kind == "interrupted" and event.confidence > 0:
            item.listens += 1
            item.last_listened = event.at

    return dict(result)


@dataclass(slots=True)
class Taste:
    contexts: dict[str, dict[str, float]] = field(default_factory=dict[str, dict[str, float]])
    artists: dict[str, float] = field(default_factory=dict[str, float])

    @classmethod
    def fit(cls, seeds: tuple[Seed, ...]) -> Taste:
        contexts: dict[str, dict[str, float]] = defaultdict(dict[str, float])
        for seed in seeds:
            for artist in seed.song.artists:
                context = contexts[seed.source]
                context[artist] = context.get(artist, 0) + seed.weight / len(seed.song.artists)

        artists: dict[str, float] = {}
        for context in contexts.values():
            scale = math.sqrt(sum(context.values()))
            if scale:
                for artist, weight in context.items():
                    artists[artist] = artists.get(artist, 0) + weight / scale

        return cls(dict(contexts), artists)

    def affinity(self, candidate: Candidate) -> float:
        features = dict.fromkeys(candidate.bridges, 0.55)
        features.update(dict.fromkeys(candidate.song.artists, 1.0))
        matches = [
            min(
                1.0,
                sum(context.get(artist, 0) * weight for artist, weight in features.items())
                / max(context.values()),
            )
            for context in self.contexts.values()
            if context
        ]
        return max(matches, default=0.0)


def _identity(song: Song) -> tuple[str, str]:
    """Filter exact title/primary-artist duplicates across releases."""
    return (" ".join(song.name.casefold().split()), song.artists[0] if song.artists else song.uri)


def training_seeds(snapshot: Snapshot, now: float) -> tuple[Seed, ...]:
    """Let explicit likes on discoveries become new retrieval anchors."""
    known = {seed.song.uri for seed in snapshot.seeds}
    songs = {song.uri: song for song in snapshot.remembered}
    songs.update({candidate.song.uri: candidate.song for candidate in snapshot.candidates})
    history = evidence(snapshot.feedback, now)
    additions = tuple(
        Seed("feedback", songs[uri], 2.0)
        for uri, item in history.items()
        if item.saved and not item.blocked and uri not in known and uri in songs
    )
    return (
        tuple(
            seed for seed in snapshot.seeds if not history.get(seed.song.uri, Evidence()).blocked
        )
        + additions
    )


def audio_taste(snapshot: Snapshot, features: tuple[AudioFeatures, ...], now: float) -> AudioTaste:
    history = evidence(snapshot.feedback, now)
    return AudioTaste(
        features,
        training_seeds(snapshot, now),
        {uri: (item.positive, item.negative) for uri, item in history.items()},
    )


def _score(
    candidate: Candidate,
    taste: Taste,
    history: dict[str, Evidence],
    artist_history: dict[str, Evidence],
    policy: Policy,
    audio: AudioTaste | None,
) -> Recommendation | None:
    song = candidate.song
    affinity = taste.affinity(candidate)
    match = audio.match(song.uri) if audio is not None else None
    if match is not None and match.affinity >= 0.35:
        affinity = max(affinity, match.affinity)
    if affinity < 0.12:
        return None

    observation = history.get(song.uri, Evidence())
    related = [(artist, 1.0) for artist in song.artists]
    related.extend((artist, 0.35) for artist in candidate.bridges if artist not in song.artists)
    learned_artists = [
        (artist_history[artist].mean - 0.5) * weight
        for artist, weight in related
        if artist in artist_history
    ]
    # A new track starts with a neutral posterior; absence of feedback is not a dislike.
    learned = observation.mean - 0.5
    known_artist = any(artist in taste.artists for artist in song.artists)
    novelty = 0.15 if known_artist else max(0.35, 1 - affinity)
    balance = math.exp(-(((novelty - policy.novelty) / 0.3) ** 2))
    population = song.monthly_listeners
    smaller = population is not None and population <= policy.smaller_artist_listeners
    rarity = 0.0
    if population is not None and smaller:
        rarity = 0.08 * (1 - population / policy.smaller_artist_listeners)
    familiarity = 0.04 / (1 + abs(observation.listens - 2)) if observation.listens else 0
    fatigue = min(0.6, 0.08 * max(0, observation.listens - 3))
    score = 0.45 * affinity + 0.28 * balance + rarity + 0.35 * learned
    if learned_artists:
        score += 0.25 * sum(learned_artists) / len(learned_artists)
    score += 0.12 * observation.uncertainty + familiarity - fatigue
    if match is not None:
        score += 0.2 * (match.affinity - 0.5) + 0.25 * match.preference

    reasons = ["Connected to artists in one of your library contexts"]
    if match is not None:
        reasons[0] = "Audio compared with recordings from your library"
        if match.preference:
            reasons.append("Similar sounds adjusted by your feedback")
    if smaller:
        reasons.append(f"Discovery artist has {population:,} monthly listeners")
    elif population is None:
        reasons.append("Artist audience size is unknown")
    if observation.listens:
        reasons.append("Spaced return to a previously observed discovery")
    if learned or learned_artists:
        reasons.append("Adjusted by your observed feedback")

    return Recommendation(song, score, affinity, novelty, tuple(reasons))


def recommend(
    snapshot: Snapshot,
    *,
    now: float,
    limit: int = 10,
    policy: Policy = Policy(),
    audio: AudioTaste | None = None,
) -> tuple[Recommendation, ...]:
    if type(limit) is not int or limit < 1 or not math.isfinite(now):
        raise ValueError("Use a positive limit and finite clock")

    seeds = training_seeds(snapshot, now)
    taste = Taste.fit(seeds)
    history = evidence(snapshot.feedback, now)
    songs = {song.uri: song for song in snapshot.remembered}
    songs.update({seed.song.uri: seed.song for seed in snapshot.seeds})
    songs.update({candidate.song.uri: candidate.song for candidate in snapshot.candidates})
    artist_history: dict[str, Evidence] = defaultdict(Evidence)
    for uri, item in history.items():
        song = songs.get(uri)
        if song is None:
            continue

        for artist in song.artists:
            artist_history[artist].positive += item.positive / len(song.artists)
            artist_history[artist].negative += item.negative / len(song.artists)
    known = {seed.song.uri for seed in seeds}
    known_titles = {_identity(seed.song) for seed in seeds}
    ranked: list[tuple[Candidate, Recommendation]] = []

    for candidate in snapshot.candidates:
        song = candidate.song
        observation = history.get(song.uri, Evidence())
        last_seen = max(snapshot.impressions.get(song.uri, -math.inf), observation.last_listened)
        if (
            song.uri in known
            or _identity(song) in known_titles
            or observation.saved
            or observation.blocked
        ):
            continue
        if now - last_seen < policy.cooldown_hours * 3600:
            continue

        result = _score(candidate, taste, history, artist_history, policy, audio)
        if result is not None:
            ranked.append((candidate, result))

    selected: list[Recommendation] = []
    artists: set[str] = set()
    bridges: set[str] = set()
    titles: set[tuple[str, str]] = set()
    discovery_target = round(limit * policy.novelty)
    discoveries = 0
    while ranked and len(selected) < limit:
        ranked.sort(
            key=lambda item: (
                -(item[1].score - 0.1 * bool(bridges.intersection(item[0].bridges))),
                item[0].song.uri,
            )
        )
        needs_discovery = len(selected) + max(0, discovery_target - discoveries) >= limit
        choice = 0
        if needs_discovery:
            choice = next(
                (
                    index
                    for index, (candidate, _) in enumerate(ranked)
                    if not any(artist in taste.artists for artist in candidate.song.artists)
                    and not artists.intersection(candidate.song.artists)
                    and _identity(candidate.song) not in titles
                ),
                0,
            )
        candidate, result = ranked.pop(choice)
        if artists.intersection(result.song.artists) or _identity(result.song) in titles:
            continue

        selected.append(result)
        discoveries += not any(artist in taste.artists for artist in result.song.artists)
        artists.update(result.song.artists)
        bridges.update(candidate.bridges)
        titles.add(_identity(result.song))

    return tuple(selected)


def split_by_artist(seeds: tuple[Seed, ...]) -> tuple[tuple[Seed, ...], tuple[Seed, ...]]:
    """Keep every song by a primary artist on one side of an evaluation split."""
    train: list[Seed] = []
    held: list[Seed] = []
    for seed in seeds:
        key = seed.song.artists[0] if seed.song.artists else seed.song.uri
        bucket = int.from_bytes(hashlib.sha256(key.encode()).digest()[:4], "big") % 5
        (held if bucket == 0 else train).append(seed)

    held_artists = {artist for seed in held for artist in seed.song.artists}
    train = [seed for seed in train if not held_artists.intersection(seed.song.artists)]

    return tuple(train), tuple(held)
