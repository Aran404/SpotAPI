"""Run real neural inference on generated tones, without copyrighted recordings.

This checks decoding, resampling, inference and determinism. It does not measure
musical understanding or recommendation quality. First run downloads model weights.
"""

from __future__ import annotations

import hashlib
import json
import math
import struct
import tempfile
import wave
from pathlib import Path

from .audio import cosine
from .extract import Encoder


def tone(path: Path, frequency: float) -> None:
    rate = 16_000
    with wave.open(str(path), "wb") as recording:
        recording.setnchannels(1)
        recording.setsampwidth(2)
        recording.setframerate(rate)
        recording.writeframes(
            b"".join(
                struct.pack("<h", int(8000 * math.sin(2 * math.pi * frequency * index / rate)))
                for index in range(rate * 12)
            )
        )


def main() -> None:
    encoder = Encoder()
    with tempfile.TemporaryDirectory(prefix="spotapi-audio-") as directory:
        path = Path(directory) / "generated-tone.wav"
        tone(path, 220)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        first = encoder.encode("spotify:track:generated", path, digest)
        repeated = encoder.encode(first.uri, path, digest)
        similarity = cosine(first.center, repeated.center)
        if similarity < 0.9999:
            raise RuntimeError("Repeated inference was not reproducible")

        tone(path, 880)
        changed = encoder.encode(first.uri, path, hashlib.sha256(path.read_bytes()).hexdigest())
        print(
            json.dumps(
                {
                    "model": first.model,
                    "dimensions": len(first.center),
                    "sections": len(first.sections),
                    "repeated_cosine": similarity,
                    "different_tone_cosine": cosine(first.center, changed.center),
                    "scope": "technical inference smoke test; no preference accuracy claim",
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
