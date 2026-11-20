"""Fast behavioral tests for the experimental discovery application."""

from __future__ import annotations

import sqlite3
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path

import pytest

from examples.taste_lab.engine import Policy, evidence, recommend, split_by_artist, training_seeds
from examples.taste_lab.evaluate import compare
from examples.taste_lab.models import Benchmark, Candidate, Feedback, Seed, Snapshot, Song
from examples.taste_lab.observe import Observer, Sample
from examples.taste_lab.store import Store

NOW = 1_000_000.0


def song(identifier: str, artist: str, *, listeners: int | None = None) -> Song:
    return Song(
        "spotify:track:" + identifier,
        identifier,
        ("spotify:artist:" + artist,),
        (artist,),
        duration_ms=120_000,
        monthly_listeners=listeners,
    )


def snapshot() -> Snapshot:
    seed = Seed("liked", song("known", "favorite"), 2)
    candidates = (
        Candidate(song("familiar", "favorite"), ()),
        Candidate(song("small", "new", listeners=10_000), ("spotify:artist:favorite",)),
        Candidate(song("popular", "large", listeners=10_000_000), ("spotify:artist:favorite",)),
        Candidate(song("unrelated", "unrelated", listeners=5), ()),
    )
    return Snapshot((seed,), candidates, (), {})


def test_discovery_requires_relevance_and_can_prefer_a_smaller_artist() -> None:
    result = recommend(snapshot(), now=NOW)

    assert result[0].song.uri == "spotify:track:small"
    assert "spotify:track:unrelated" not in {item.song.uri for item in result}
    assert all(item.song.uri != "spotify:track:known" for item in result)


def test_recommendations_are_pure_and_displaying_a_song_is_not_listening() -> None:
    data = snapshot()
    first = recommend(data, now=NOW)
    assert recommend(data, now=NOW) == first
    data = replace(data, impressions={first[0].song.uri: NOW})

    assert first[0].song.uri not in {item.song.uri for item in recommend(data, now=NOW + 3600)}
    assert evidence(data.feedback, NOW) == {}
    assert first[0].song.uri in {item.song.uri for item in recommend(data, now=NOW + 49 * 3600)}


def test_explicit_dislike_blocks_a_song_but_unseen_songs_remain_neutral() -> None:
    data = snapshot()
    event = Feedback("explicit", "spotify:track:small", "dislike", NOW)
    result = recommend(replace(data, feedback=(event,)), now=NOW)

    assert event.uri not in {item.song.uri for item in result}
    assert evidence((event,), NOW)[event.uri].negative == 4
    assert evidence((), NOW) == {}


def test_a_liked_discovery_becomes_a_new_retrieval_anchor() -> None:
    data = snapshot()
    event = Feedback("save", "spotify:track:small", "like", NOW)
    data = replace(data, feedback=(event,))
    seeds = training_seeds(data, NOW)

    assert any(seed.song.uri == event.uri for seed in seeds)
    assert event.uri not in {item.song.uri for item in recommend(data, now=NOW)}


def test_liked_discovery_remains_an_anchor_after_candidate_refresh(tmp_path: Path) -> None:
    store = Store(tmp_path / "profile.sqlite3")
    discovery = song("discovery", "new")
    store.replace_candidates([Candidate(discovery, ())])
    store.record(Feedback("like", discovery.uri, "like", NOW))
    store.replace_candidates([])

    assert training_seeds(store.snapshot(), NOW) == (Seed("feedback", discovery, 2),)


def test_partial_candidate_credits_do_not_rewrite_the_imported_library(tmp_path: Path) -> None:
    store = Store(tmp_path / "profile.sqlite3")
    imported = replace(song("collaboration", "a"), artists=("a", "b"), artist_names=("A", "B"))
    store.replace_source("liked", [imported], 2)
    store.replace_candidates(
        [Candidate(replace(imported, artists=("a",), artist_names=("A",)), ())]
    )

    assert store.snapshot().seeds[0].song == imported


def test_unlike_is_not_treated_as_an_explicit_dislike() -> None:
    events = (
        Feedback("1", "spotify:track:test", "like", NOW - 1),
        Feedback("2", "spotify:track:test", "unsave", NOW),
    )
    observation = evidence(events, NOW)["spotify:track:test"]

    assert not observation.saved and not observation.blocked
    assert observation.negative == 0


def test_future_feedback_cannot_influence_a_historical_ranking() -> None:
    data = snapshot()
    future = Feedback("future", "spotify:track:small", "dislike", NOW + 1)

    assert recommend(replace(data, feedback=(future,)), now=NOW) == recommend(data, now=NOW)


def test_slate_limits_artist_repetition_and_duplicate_releases() -> None:
    data = snapshot()
    extra = Candidate(song("other", "new"), ("spotify:artist:favorite",))
    duplicate = Candidate(
        replace(extra.song, uri="spotify:track:duplicate", name="small"), extra.bridges
    )
    result = recommend(replace(data, candidates=data.candidates + (extra, duplicate)), now=NOW)

    artists = [artist for item in result for artist in item.song.artists]
    assert len(artists) == len(set(artists))


def test_novelty_budget_reserves_room_for_relevant_unfamiliar_artists() -> None:
    seeds = tuple(Seed("liked", song("known" + str(i), str(i)), 2) for i in range(8))
    candidates = tuple(Candidate(song("deep" + str(i), str(i)), ()) for i in range(8))
    candidates += tuple(
        Candidate(song("discovery" + str(i), "new" + str(i)), ("spotify:artist:0",))
        for i in range(8)
    )
    result = recommend(Snapshot(seeds, candidates, (), {}), now=NOW, limit=6)
    assert sum(item.song.artist_names[0].startswith("new") for item in result) >= 3


def sample(
    position: int, *, uri: str = "a", duration: int = 120_000, playing: bool = True
) -> Sample:
    return Sample(
        "spotify:track:" + uri, "occurrence-" + uri, "device", position, duration, playing
    )


def test_a_short_observed_transition_is_only_weak_negative_evidence() -> None:
    observer = Observer()
    for second in range(11):
        assert observer.observe(sample(second * 1000), clock=second, at=NOW + second) is None

    event = observer.observe(sample(0, uri="b"), clock=11, at=NOW + 11)
    assert event is not None and event.kind == "early_transition"
    assert event.confidence == 0.25


def test_completion_requires_observing_most_of_the_track() -> None:
    observer = Observer()
    for second in range(10):
        observer.observe(sample(second * 1000, duration=10_000), clock=second, at=NOW + second)

    event = observer.observe(sample(0, uri="b"), clock=10, at=NOW + 10)
    assert event is not None and event.kind == "complete"

    late = Observer()
    late.observe(sample(115_000), clock=0, at=NOW)
    late.observe(sample(116_000), clock=1, at=NOW + 1)
    assert late.observe(sample(0, uri="b"), clock=2, at=NOW + 2) is None


@pytest.mark.parametrize("interruption", ["disconnect", "gap", "device", "pause"])
def test_interruptions_do_not_turn_into_dislikes(interruption: str) -> None:
    observer = Observer()
    for second in range(11):
        observer.observe(sample(second * 1000), clock=second, at=NOW + second)

    next_sample: Sample | None = sample(0, uri="b")
    clock = 11
    if interruption == "disconnect":
        next_sample = None
    elif interruption == "gap":
        clock = 20
    elif interruption == "device":
        next_sample = replace(sample(0, uri="b"), device="phone")
    else:
        observer.observe(sample(10_000, playing=False), clock=11, at=NOW + 11)
        clock = 12

    event = observer.observe(next_sample, clock=clock, at=NOW + clock)
    assert event is not None and event.kind == "interrupted"
    assert evidence((event,), NOW + clock)[event.uri].negative == 0


def test_seeked_playback_is_not_mislabeled_as_completion_or_skip() -> None:
    observer = Observer()
    for second in range(7):
        observer.observe(sample(second * 1000), clock=second, at=NOW + second)
    observer.observe(sample(100_000), clock=7, at=NOW + 7)
    event = observer.observe(sample(0, uri="b"), clock=8, at=NOW + 8)

    assert event is not None and event.kind == "interrupted"


def test_store_retries_do_not_duplicate_feedback_and_sync_replaces_membership(
    tmp_path: Path,
) -> None:
    store = Store(tmp_path / "profile.sqlite3")
    first, second = song("first", "a"), song("second", "b")
    store.replace_source("liked", [first], 2)
    store.replace_source("playlist", [first, second], 0.75)
    event = Feedback("unique", first.uri, "complete", NOW)
    store.record(event)
    store.record(event)
    store.replace_source("liked", [second], 2)
    store.remove_stale_sources({"liked"})
    current = store.snapshot()

    assert len(current.feedback) == 1
    assert current.seeds == (Seed("liked", second, 2),)


def test_failed_source_write_rolls_back_all_its_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = Store(tmp_path / "profile.sqlite3")
    first, second = song("first", "a"), song("second", "b")
    store.replace_source("liked", [first], 2)
    original = Store._songs

    def failed(db: sqlite3.Connection, songs: Sequence[Song]) -> None:
        original(db, songs)
        raise OSError("disk failure")

    monkeypatch.setattr(Store, "_songs", staticmethod(failed))
    with pytest.raises(OSError):
        store.replace_source("liked", [second], 2)

    assert store.snapshot().seeds == (Seed("liked", first, 2),)


def test_artist_split_drops_collaboration_overlap_and_evaluation_rejects_leakage() -> None:
    seeds = tuple(Seed("liked", song(str(i), str(i)), 2) for i in range(100))
    train, held = split_by_artist(seeds)
    assert train and held
    assert not {a for seed in train for a in seed.song.artists}.intersection(
        a for seed in held for a in seed.song.artists
    )
    with pytest.raises(ValueError, match="track identities"):
        compare(train, train, ())


def test_evaluation_reports_unavailable_ranking_when_retrieval_misses_positives() -> None:
    result = compare(
        (Seed("liked", song("train", "a"), 2),), (Seed("liked", song("held", "b"), 2),), ()
    )

    assert result.retrieval_recall == 0
    assert result.ranking_recall is None
    assert result.random_mean_hits == 0


def test_frozen_evaluation_pool_is_independent_of_production_refresh(tmp_path: Path) -> None:
    store = Store(tmp_path / "profile.sqlite3")
    data = snapshot()
    benchmark = Benchmark(data.seeds, (), data.candidates)
    with pytest.raises(ValueError, match="online evaluate"):
        store.benchmark()
    store.save_benchmark(benchmark)
    store.replace_candidates([])

    assert store.benchmark() == benchmark
    assert store.snapshot().candidates == ()


def test_evaluation_baselines_are_independent_of_network_completion_order() -> None:
    train = (Seed("liked", song("train", "train"), 2),)
    held = tuple(Seed("liked", song(str(i), str(i)), 2) for i in range(10))
    candidates = tuple(Candidate(song(str(i), str(i)), ()) for i in range(50))

    assert compare(train, held, candidates) == compare(train, held, tuple(reversed(candidates)))


@pytest.mark.parametrize("novelty", [float("nan"), -0.1, 1.1])
def test_policy_rejects_invalid_novelty(novelty: float) -> None:
    with pytest.raises(ValueError):
        Policy(novelty=novelty)
