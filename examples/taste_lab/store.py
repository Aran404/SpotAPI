"""Local SQLite transactions; credentials are never accepted by this layer."""

from __future__ import annotations

import json
import math
import sqlite3
from collections.abc import Generator, Sequence
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from spotapi import from_dict

from .audio import AudioFeatures
from .models import Benchmark, Candidate, Feedback, Seed, Snapshot, Song


class Store:
    """Open a connection per operation, allowing async callers to use to_thread."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS songs (uri TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS seeds (
                    source TEXT NOT NULL, uri TEXT NOT NULL, weight REAL NOT NULL,
                    PRIMARY KEY (source, uri)
                );
                CREATE TABLE IF NOT EXISTS candidates (
                    uri TEXT PRIMARY KEY, bridges TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS feedback (
                    id TEXT PRIMARY KEY, uri TEXT NOT NULL, kind TEXT NOT NULL,
                    at REAL NOT NULL, confidence REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS impressions (uri TEXT PRIMARY KEY, at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS audio (uri TEXT PRIMARY KEY, data TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS audio_attempts (
                    uri TEXT PRIMARY KEY, status TEXT NOT NULL, at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS benchmark (id INTEGER PRIMARY KEY, data TEXT NOT NULL);
            """)

    @contextmanager
    def connection(self) -> Generator[sqlite3.Connection, None, None]:
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    @staticmethod
    def _songs(db: sqlite3.Connection, songs: Sequence[Song]) -> None:
        db.executemany(
            "INSERT INTO songs VALUES (?, ?) ON CONFLICT(uri) DO UPDATE SET data=excluded.data",
            [(song.uri, json.dumps(asdict(song), allow_nan=False)) for song in songs],
        )

    def replace_source(self, source: str, songs: Sequence[Song], weight: float) -> None:
        """Replace a complete source atomically; a failed import leaves its old data."""
        if not math.isfinite(weight) or weight <= 0:
            raise ValueError("Source weight must be finite and positive")

        with self.connection() as db:
            self._songs(db, songs)
            db.execute("DELETE FROM seeds WHERE source=?", (source,))
            db.executemany(
                "INSERT OR REPLACE INTO seeds VALUES (?, ?, ?)",
                [(source, song.uri, weight) for song in songs],
            )

    def remove_stale_sources(self, current: set[str]) -> None:
        with self.connection() as db:
            previous = {row[0] for row in db.execute("SELECT DISTINCT source FROM seeds")}
            db.executemany(
                "DELETE FROM seeds WHERE source=?", [(source,) for source in previous - current]
            )

    def replace_candidates(self, candidates: Sequence[Candidate]) -> None:
        """Publish a candidate pool together with its retrieval evidence."""
        with self.connection() as db:
            imported = {row[0] for row in db.execute("SELECT DISTINCT uri FROM seeds")}
            # Artist top-track responses can omit collaborators. Never let those
            # partial credits rewrite authoritative imported library metadata.
            self._songs(
                db,
                [candidate.song for candidate in candidates if candidate.song.uri not in imported],
            )
            db.execute("DELETE FROM candidates")
            db.executemany(
                "INSERT INTO candidates VALUES (?, ?)",
                [(candidate.song.uri, json.dumps(candidate.bridges)) for candidate in candidates],
            )

    def record(self, event: Feedback) -> None:
        if (
            not math.isfinite(event.at)
            or not math.isfinite(event.confidence)
            or not 0 <= event.confidence <= 1
        ):
            raise ValueError("Feedback needs a finite timestamp and confidence from 0 to 1")

        if event.kind not in {
            "like",
            "dislike",
            "complete",
            "early_transition",
            "interrupted",
            "unsave",
        }:
            raise ValueError("Unknown feedback kind")

        with self.connection() as db:
            inserted = db.execute(
                "INSERT OR IGNORE INTO feedback VALUES (?, ?, ?, ?, ?)",
                (event.id, event.uri, event.kind, event.at, event.confidence),
            )
            if inserted.rowcount and event.kind == "unsave":
                db.execute("DELETE FROM seeds WHERE source='liked' AND uri=?", (event.uri,))

    def shown(self, songs: Sequence[Song], at: float) -> None:
        with self.connection() as db:
            db.executemany(
                "INSERT INTO impressions VALUES (?, ?) ON CONFLICT(uri) DO UPDATE SET at=excluded.at",
                [(song.uri, at) for song in songs],
            )

    def save_audio(self, features: AudioFeatures) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO audio VALUES (?, ?) ON CONFLICT(uri) DO UPDATE SET data=excluded.data",
                (features.uri, json.dumps(asdict(features), allow_nan=False)),
            )

    def audio_features(self) -> tuple[AudioFeatures, ...]:
        with self.connection() as db:
            return tuple(
                from_dict(AudioFeatures, json.loads(data))
                for (data,) in db.execute("SELECT data FROM audio ORDER BY uri")
            )

    def audio_attempt(self, uri: str, status: str, at: float) -> None:
        if status not in {"unmatched", "failed"} or not math.isfinite(at):
            raise ValueError("Use a known audio attempt status and a finite timestamp")

        with self.connection() as db:
            db.execute(
                "INSERT INTO audio_attempts VALUES (?, ?, ?) "
                "ON CONFLICT(uri) DO UPDATE SET status=excluded.status, at=excluded.at",
                (uri, status, at),
            )

    def deferred_audio(self, now: float) -> set[str]:
        with self.connection() as db:
            return {
                uri
                for uri, status, at in db.execute("SELECT uri, status, at FROM audio_attempts")
                if 0 <= now - at < (86_400 if status == "unmatched" else 3600)
            }

    def save_benchmark(self, benchmark: Benchmark) -> None:
        with self.connection() as db:
            db.execute(
                "INSERT INTO benchmark VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (json.dumps(asdict(benchmark), allow_nan=False),),
            )

    def benchmark(self) -> Benchmark:
        with self.connection() as db:
            row = db.execute("SELECT data FROM benchmark WHERE id=1").fetchone()
            if row is None:
                raise ValueError("Run an online evaluate once before using --cached")
            return from_dict(Benchmark, json.loads(row[0]))

    def snapshot(self) -> Snapshot:
        with self.connection() as db:
            db.execute("BEGIN")
            songs = {
                uri: from_dict(Song, json.loads(data))
                for uri, data in db.execute("SELECT uri, data FROM songs")
            }
            seeds = tuple(
                Seed(source, songs[uri], weight)
                for source, uri, weight in db.execute("SELECT source, uri, weight FROM seeds")
            )
            candidates = tuple(
                Candidate(songs[uri], tuple(json.loads(bridges)))
                for uri, bridges in db.execute("SELECT uri, bridges FROM candidates")
            )
            feedback = tuple(
                from_dict(
                    Feedback,
                    dict(zip(("id", "uri", "kind", "at", "confidence"), row, strict=True)),
                )
                for row in db.execute(
                    "SELECT id, uri, kind, at, confidence FROM feedback ORDER BY at, id"
                )
            )
            impressions = dict(db.execute("SELECT uri, at FROM impressions"))

        return Snapshot(seeds, candidates, feedback, impressions, tuple(songs.values()))
