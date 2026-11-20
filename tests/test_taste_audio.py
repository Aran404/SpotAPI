"""Audio learning contracts; synthetic vectors test mechanics, not music enjoyment."""

from __future__ import annotations

import json
import math
from dataclasses import replace
from pathlib import Path

import pytest

from examples.taste_lab.audio import AudioFeatures, AudioTaste, unit
from examples.taste_lab.engine import audio_taste, recommend
from examples.taste_lab.extract import manifest
from examples.taste_lab.models import Candidate, Feedback, Seed, Snapshot, Song
from examples.taste_lab.store import Store


def song(name: str) -> Song:
    return Song(f"spotify:track:{name}", name, (f"spotify:artist:{name}",), (name,))


def features(name: str, vector: tuple[float, ...]) -> AudioFeatures:
    return AudioFeatures(song(name).uri, "test-model@revision/pipeline", "digest", (vector,))


@pytest.mark.parametrize("values", [(), (0.0, 0.0), (float("nan"),), (float("inf"),)])
def test_invalid_embeddings_fail_before_ranking(values: tuple[float, ...]) -> None:
    with pytest.raises(ValueError):
        unit(values)


def test_models_and_dimensions_cannot_be_silently_mixed() -> None:
    first = features("first", (1, 0))
    with pytest.raises(ValueError, match="different audio"):
        AudioTaste((first, replace(first, model="other")), (), {})
    with pytest.raises(ValueError, match="different audio"):
        AudioTaste((first, features("second", (1, 0, 0))), (), {})


def test_distinct_taste_clusters_survive_cold_start() -> None:
    seeds = tuple(Seed("liked", song(name), 2) for name in ("quiet", "loud"))
    data = (
        features("quiet", (1, 0)),
        features("loud", (0, 1)),
        features("quiet-discovery", (1, 0)),
        features("loud-discovery", (0, 1)),
    )
    taste = AudioTaste(data, seeds, {})
    quiet, loud = taste.match(song("quiet-discovery").uri), taste.match(song("loud-discovery").uri)

    assert quiet is not None and loud is not None
    assert quiet.affinity == loud.affinity and quiet.affinity > 0.8
    assert taste.match("missing") is None
    assert AudioTaste(data, (), {}).match(song("loud").uri) is None


def test_feedback_generalizes_to_similar_audio_without_treating_unknown_as_negative() -> None:
    data = (features("seed", (1, 0)), features("rated", (1, 0)), features("new", (1, 0)))
    seeds = (Seed("liked", song("seed"), 2),)
    positive = AudioTaste(data, seeds, {song("rated").uri: (3, 0)}).match(song("new").uri)
    negative = AudioTaste(data, seeds, {song("rated").uri: (0, 4)}).match(song("new").uri)
    neutral = AudioTaste(data, seeds, {}).match(song("new").uri)

    assert positive is not None and negative is not None and neutral is not None
    assert positive.preference > neutral.preference == 0 > negative.preference


def test_audio_can_find_a_relevant_artist_without_an_artist_graph_edge() -> None:
    snapshot = Snapshot((Seed("liked", song("seed"), 2),), (Candidate(song("new"), ()),), (), {})
    data = (features("seed", (1, 0)), features("new", (1, 0)))
    assert not recommend(snapshot, now=100)
    assert recommend(snapshot, now=100, audio=audio_taste(snapshot, data, 100))
    assert recommend(snapshot, now=100, audio=audio_taste(snapshot, (), 100)) == ()


def test_future_feedback_does_not_leak_into_audio_preferences() -> None:
    snapshot = Snapshot(
        (Seed("liked", song("seed"), 2),),
        (Candidate(song("new"), ()),),
        (Feedback("future", song("seed").uri, "dislike", 101),),
        {},
    )
    data = (features("seed", (1, 0)), features("new", (1, 0)))
    assert audio_taste(snapshot, data, 100).match(song("new").uri) is not None
    assert audio_taste(snapshot, data, 101).match(song("new").uri) is None


def test_audio_round_trip_and_replacement(tmp_path: Path) -> None:
    store = Store(tmp_path / "taste.sqlite3")
    first = features("seed", (2, 0))
    store.save_audio(first)
    assert store.audio_features() == (first,)
    replacement = replace(first, digest="new-recording", sections=((0, 3),))
    store.save_audio(replacement)
    assert store.audio_features() == (replacement,)


def test_large_library_audio_index_agrees_with_small_library_path() -> None:
    data = tuple(features(str(index), (1, index / 40)) for index in range(40))
    seeds = tuple(Seed("liked", song(str(index)), 2) for index in range(40))
    candidate = features("candidate", (1, 0))
    accelerated = AudioTaste(data + (candidate,), seeds, {}).match(candidate.uri)
    # The three closest examples are the same in either library.
    ordinary = AudioTaste(data[:3] + (candidate,), seeds[:3], {}).match(candidate.uri)

    assert accelerated is not None and ordinary is not None
    assert math.isclose(accelerated.affinity, ordinary.affinity, abs_tol=1e-6)


def test_manifest_resolves_relative_files_and_rejects_missing_or_duplicate_tracks(
    tmp_path: Path,
) -> None:
    track = "4uLU6hMCjMI75M1A2tKUQC"
    path = tmp_path / "audio.json"
    audio = tmp_path / "song.wav"
    audio.write_bytes(b"test")
    path.write_text(json.dumps({f"spotify:track:{track}": "song.wav"}), encoding="utf-8")
    assert manifest(path) == ((f"spotify:track:{track}", audio.resolve()),)
    path.write_text(json.dumps({f"spotify:track:{track}": "absent.wav"}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        manifest(path)
    path.write_text(
        json.dumps(
            {
                f"spotify:track:{track}": "song.wav",
                f"https://open.spotify.com/track/{track}": "song.wav",
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        manifest(path)
