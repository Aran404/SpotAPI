"""Optional CPU audio inference. Heavy dependencies load only for audio-import."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
from pathlib import Path
from typing import Any, cast

from spotapi.resources import parse_spotify_resource

from .audio import AudioFeatures, Vector, unit
from .store import Store

MODEL = "laion/clap-htsat-unfused"
REVISION = "8fa0f1c6d0433df6e97c127f64b2a1d6c0dcda8a"
IDENTITY = f"{MODEL}@{REVISION}/sections-v1"


def manifest(path: Path) -> tuple[tuple[str, Path], ...]:
    """Resolve manually verified Spotify-to-recording mappings; never guess a match."""
    raw: object = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not raw:
        raise ValueError("Use a nonempty JSON object mapping track URLs/URIs to local audio paths")

    entries: dict[str, Path] = {}
    for track, filename in cast(dict[object, object], raw).items():
        if not isinstance(track, str) or not isinstance(filename, str):
            raise ValueError("Manifest keys and filenames must be strings")

        uri = parse_spotify_resource(track, "track").uri
        audio_path = (path.parent / filename).resolve()
        if uri in entries or not audio_path.is_file():
            raise ValueError("Manifest contains a duplicate track or missing audio file")

        entries[uri] = audio_path

    return tuple(entries.items())


class Encoder:
    """Isolate untyped third-party inference APIs from the typed recommendation core."""

    def __init__(self) -> None:
        try:
            self.torch: Any = importlib.import_module("torch")
            self.sf: Any = importlib.import_module("soundfile")
            self.np: Any = importlib.import_module("numpy")
            self.signal: Any = importlib.import_module("scipy.signal")
            transformers = importlib.import_module("transformers")
        except ImportError as error:
            raise RuntimeError(
                "Install examples/taste_lab/requirements-audio.txt first"
            ) from error

        self.processor: Any = transformers.ClapFeatureExtractor.from_pretrained(
            MODEL, revision=REVISION
        )
        self.model: Any = transformers.ClapModel.from_pretrained(
            MODEL, revision=REVISION, weights_only=True
        ).eval()
        self.torch.set_num_threads(min(4, self.torch.get_num_threads()))

    def encode(self, uri: str, path: Path, digest: str) -> AudioFeatures:
        sections: list[Vector] = []
        with self.sf.SoundFile(str(path)) as recording:
            rate = int(recording.samplerate)
            frames = int(recording.frames)
            if rate < 8000 or frames / rate < 2 or recording.channels > 8:
                raise ValueError("Use at least two seconds of audio with a supported sample rate")

            size = min(frames, 10 * rate)
            starts = sorted({int((frames - size) * fraction) for fraction in (0.1, 0.5, 0.9)})
            for start in starts:
                recording.seek(start)
                audio = recording.read(size, dtype="float32", always_2d=True).mean(axis=1)
                if (
                    not self.np.isfinite(audio).all()
                    or float(self.np.max(self.np.abs(audio))) < 1e-6
                ):
                    raise ValueError("Recording contains a silent or invalid analysis section")

                divisor = math.gcd(rate, 48_000)
                audio = self.signal.resample_poly(audio, 48_000 // divisor, rate // divisor)
                inputs = self.processor(
                    audio, sampling_rate=48_000, return_tensors="pt", truncation="rand_trunc"
                )
                with self.torch.inference_mode():
                    result = self.model.get_audio_features(**inputs)
                sections.append(unit(result[0].cpu().tolist()))

        return AudioFeatures(uri, IDENTITY, digest, tuple(sections))


def import_audio(store: Store, path: Path) -> tuple[int, int]:
    """Checkpoint each completed recording; reruns reuse content-addressed results."""
    entries = manifest(path)
    existing = {item.uri: item for item in store.audio_features()}
    snapshot = store.snapshot()
    known = {seed.song.uri for seed in snapshot.seeds} | {
        item.song.uri for item in snapshot.candidates
    }
    if any(uri not in known for uri, _ in entries):
        raise ValueError("Import or retrieve manifest tracks before attaching audio")

    encoder: Encoder | None = None
    imported, reused = 0, 0
    for index, (uri, audio_path) in enumerate(entries, 1):
        with audio_path.open("rb") as recording:
            digest = hashlib.file_digest(recording, "sha256").hexdigest()
        previous = existing.get(uri)
        if previous and previous.digest == digest and previous.model == IDENTITY:
            reused += 1
            continue

        encoder = encoder or Encoder()
        features = encoder.encode(uri, audio_path, digest)
        store.save_audio(features)
        imported += 1
        print(f"Analyzed recording {index}/{len(entries)} ({len(features.sections)} sections)")

    return imported, reused
