"""Optional, temporary audio sampling with conservative recording matching.

This adapter does not establish recording rights or bypass access restrictions.
It uses no account cookies, and never shares Spotify credentials with YouTube.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, replace
from pathlib import Path
from typing import cast

from .engine import Policy, recommend
from .extract import IDENTITY, Encoder
from .models import Snapshot, Song
from .store import Store


def normalized(value: str) -> str:
    return " ".join(re.findall(r"\w+", unicodedata.normalize("NFKC", value).casefold()))


@dataclass(frozen=True, slots=True)
class Recording:
    video_id: str
    duration: float

    @property
    def url(self) -> str:
        return "https://www.youtube.com/watch?v=" + self.video_id


def match(song: Song, entries: list[object], *, verified: bool = True) -> Recording | None:
    """Accept exact title + primary-artist Topic channel + close duration only.

    Metadata is supporting evidence, not an acoustic fingerprint. Conflicting
    equally plausible recordings are skipped rather than selected by view count.
    """
    if not song.artist_names or song.duration_ms <= 0:
        return None

    artist = normalized(song.artist_names[0])
    title = normalized(song.name)
    matches: dict[str, Recording] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            continue

        item = cast(dict[str, object], entry)
        video_id, name, channel = item.get("id"), item.get("title"), item.get("channel")
        duration = item.get("duration")
        if not all(isinstance(value, str) for value in (video_id, name, channel)):
            continue
        if not isinstance(duration, (int, float)) or not math.isfinite(duration):
            continue

        assert isinstance(video_id, str) and isinstance(name, str) and isinstance(channel, str)
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            continue
        topic = normalized(channel) == artist + " topic"
        official = normalized(channel) == artist and (
            not verified or item.get("channel_is_verified") is True
        )
        clean_title = re.sub(
            r"\s*[\[(](?:official audio|audio|official music video|official video)[\])]\s*$",
            "",
            name,
            flags=re.IGNORECASE,
        )
        titles = {normalized(clean_title)}
        prefix = artist + " "
        if normalized(clean_title).startswith(prefix):
            titles.add(normalized(clean_title)[len(prefix) :])
        if not (topic or official) or title not in titles:
            continue
        if abs(duration * 1000 - song.duration_ms) > max(3000, song.duration_ms * 0.02):
            continue

        matches[video_id] = Recording(video_id, duration)

    return next(iter(matches.values())) if len(matches) == 1 else None


def _run(arguments: list[str], *, timeout: int = 90) -> str:
    result = subprocess.run(
        arguments, capture_output=True, text=True, encoding="utf-8", timeout=timeout
    )
    if result.returncode:
        # Downloader errors can contain signed media URLs; do not echo them to logs.
        raise RuntimeError("Audio source request failed; the track was left unchanged")

    return result.stdout


def find(song: Song) -> Recording | None:
    if not song.artist_names:
        return None

    query = f"ytsearch10:{song.artist_names[0]} {song.name} Topic"
    response: object = json.loads(
        _run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--dump-single-json",
                "--skip-download",
                "--flat-playlist",
                "--quiet",
                "--no-warnings",
                "--",
                query,
            ]
        )
    )
    if not isinstance(response, dict):
        raise ValueError("Audio search returned an invalid response")

    entries = cast(dict[str, object], response).get("entries")
    if not isinstance(entries, list):
        return None

    rows = cast(list[object], entries)
    direct = match(song, rows)
    if direct is not None:
        return direct

    possible = match(song, rows, verified=False)
    if possible is None:
        return None

    metadata: object = json.loads(
        _run(
            [
                sys.executable,
                "-m",
                "yt_dlp",
                "--dump-single-json",
                "--skip-download",
                "--quiet",
                "--no-warnings",
                "--",
                possible.url,
            ]
        )
    )
    return match(song, [metadata])


def _sample(recording: Recording, directory: Path) -> tuple[Path, int]:
    binary = importlib.import_module("imageio_ffmpeg").get_ffmpeg_exe()
    start = max(0, min(recording.duration * 0.45, recording.duration - 12))
    end = min(recording.duration, start + 12)
    _run(
        [
            sys.executable,
            "-m",
            "yt_dlp",
            "--quiet",
            "--no-warnings",
            "--no-playlist",
            "--socket-timeout",
            "15",
            "--retries",
            "1",
            "--fragment-retries",
            "1",
            "--max-filesize",
            "30M",
            "--ffmpeg-location",
            str(binary),
            "--download-sections",
            f"*{start:.3f}-{end:.3f}",
            "-f",
            "bestaudio/best",
            "-o",
            str(directory / "source.%(ext)s"),
            "--",
            recording.url,
        ]
    )
    files = [path for path in directory.glob("source.*") if path.suffix not in {".part", ".ytdl"}]
    if len(files) != 1:
        raise RuntimeError("Audio source did not return one complete sample")

    output = directory / "sample.wav"
    _run(
        [
            str(binary),
            "-nostdin",
            "-loglevel",
            "error",
            "-i",
            str(files[0]),
            "-t",
            "12",
            "-ac",
            "1",
            "-ar",
            "48000",
            str(output),
        ]
    )
    return output, round(start * 1000)


def selection(
    snapshot: Snapshot, limit: int, *, exclude: set[str] | None = None
) -> tuple[Song, ...]:
    """Alternate library anchors and discoveries, spreading the initial audio budget."""
    if not 1 <= limit <= 200:
        raise ValueError("Analyze between 1 and 200 recordings per run")

    seeds = sorted(snapshot.seeds, key=lambda seed: (-seed.weight, seed.song.uri))
    known = {seed.song.uri for seed in seeds}
    ranked = recommend(snapshot, now=time.time(), limit=200, policy=Policy(cooldown_hours=0))
    discoveries = [item.song for item in ranked]
    prioritized = {song.uri for song in discoveries}
    discoveries.extend(
        item.song
        for item in snapshot.candidates
        if item.song.uri not in known and item.song.uri not in prioritized
    )
    pools = ([seed.song for seed in seeds], discoveries)
    result: list[Song] = []
    seen: set[str] = set(exclude or ())
    artists: set[str] = set()
    for diverse in (True, False):
        queues = [iter(pool) for pool in pools]
        active = [True, True]
        while any(active) and len(result) < limit:
            for index, queue in enumerate(queues):
                for song in queue:
                    if song.uri in seen or not song.artist_names or song.duration_ms <= 0:
                        continue
                    if diverse and artists.intersection(song.artists):
                        continue

                    result.append(song)
                    seen.add(song.uri)
                    artists.update(song.artists)
                    break
                else:
                    active[index] = False
                if len(result) >= limit:
                    break

    return tuple(result)


def enrich(store: Store, *, limit: int, force: bool = False) -> Mapping[str, int]:
    try:
        importlib.import_module("yt_dlp")
        importlib.import_module("imageio_ffmpeg")
    except ImportError as error:
        raise RuntimeError("Install examples/taste_lab/requirements-audio.txt first") from error

    existing = {item.uri: item for item in store.audio_features()}
    cached = (
        {uri for uri, item in existing.items() if item.model == IDENTITY}
        if not force
        else set[str]()
    )
    deferred = set[str]() if force else store.deferred_audio(time.time())
    counts = {
        "analyzed": 0,
        "cached": len(cached),
        "deferred": len(deferred),
        "unmatched": 0,
        "failed": 0,
    }
    encoder: Encoder | None = None
    songs = selection(store.snapshot(), limit, exclude=cached | deferred)
    for index, song in enumerate(songs, 1):
        previous = existing.get(song.uri)
        if previous and previous.model == IDENTITY and not force:
            counts["cached"] += 1
            continue

        try:
            recording = find(song)
            if recording is None:
                counts["unmatched"] += 1
                store.audio_attempt(song.uri, "unmatched", time.time())
                print(f"Audio {index}/{len(songs)}: no unambiguous recording match")
                continue

            with tempfile.TemporaryDirectory(prefix="spotapi-preview-") as temporary:
                path, offset = _sample(recording, Path(temporary))
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                encoder = encoder or Encoder()
                features = encoder.encode(song.uri, path, digest)
                store.save_audio(replace(features, source_url=recording.url, offset_ms=offset))
            counts["analyzed"] += 1
            print(f"Audio {index}/{len(songs)}: analyzed temporary sample")
        except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
            counts["failed"] += 1
            store.audio_attempt(song.uri, "failed", time.time())
            print(f"Audio {index}/{len(songs)}: source unavailable; previous data retained")

    return counts
