"""Local music discovery. Run python -m examples.taste_lab --help."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from uuid import uuid4

from spotapi import AsyncClient, Catalogue, Player
from spotapi.models import PlayerState
from spotapi.resources import parse_spotify_resource
from spotapi.types import SpotAPIError

from .engine import Policy, audio_taste, recommend, split_by_artist, training_seeds
from .evaluate import compare
from .models import Benchmark, Feedback, FeedbackKind
from .observe import Observer, Sample
from .spotify import retrieve, sync_library
from .store import Store


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path.home() / ".spotapi" / "taste-lab.sqlite3")
    parser.add_argument(
        "--env-file", type=Path, help="Read SPOTIFY_COOKIE using optional python-dotenv"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser(
        "sync", help="import all accessible library playlists, albums and liked tracks"
    )
    for command in ("refresh", "evaluate"):
        refresh = commands.add_parser(
            command,
            help=(
                "retrieve candidates"
                if command == "refresh"
                else "run an artist-disjoint retrospective comparison"
            ),
        )
        refresh.add_argument("--seed-artists", type=int, default=8)
        refresh.add_argument("--neighbors", type=int, default=5)
        if command == "evaluate":
            refresh.add_argument(
                "--cached",
                action="store_true",
                help="reuse the last isolated evaluation pool without network requests",
            )

    recommendations = commands.add_parser("recommend", help="rank locally cached discoveries")
    recommendations.add_argument("--limit", type=int, default=10)
    recommendations.add_argument("--novelty", type=float, default=0.45)
    recommendations.add_argument("--cooldown-hours", type=float, default=48)
    recommendations.add_argument("--json", action="store_true")
    recommendations.add_argument(
        "--metadata-only", action="store_true", help="disable audio for comparison"
    )
    recommendations.add_argument(
        "--dry-run", action="store_true", help="leave impression history unchanged"
    )
    feedback = commands.add_parser("feedback", help="record an explicit local opinion")
    feedback.add_argument("track", help="an imported or recommended Spotify track")
    feedback.add_argument("kind", choices=("like", "dislike", "skip"))
    commands.add_parser(
        "observe", help="observe an existing player; record weak listening evidence"
    )
    commands.add_parser("status", help="show local counts without signing in")
    audio = commands.add_parser("audio-import", help="analyze manually matched local recordings")
    audio.add_argument("manifest", type=Path, help="JSON mapping track URLs to local audio paths")
    enrichment = commands.add_parser(
        "enrich", help="match recordings and analyze temporary audio samples"
    )
    enrichment.add_argument("--limit", type=int, default=20)
    enrichment.add_argument("--force", action="store_true", help="recompute cached recordings")
    return parser


def _sample(state: PlayerState | None) -> Sample | None:
    if (
        state is None
        or state.track is None
        or state.active_device_id is None
        or not state.track.uri.startswith("spotify:track:")
    ):
        return None

    return Sample(
        state.track.uri,
        state.track.uid,
        state.active_device_id,
        state.position_ms,
        state.duration_ms,
        state.is_playing and not state.is_paused,
    )


async def observe(player: Player, store: Store) -> None:
    observer = Observer()

    @player.event
    async def on_library_change(uri: str, saved: bool) -> None:
        kind: FeedbackKind = "like" if saved else "unsave"
        await asyncio.to_thread(store.record, Feedback(str(uuid4()), uri, kind, time.time()))

    runner = asyncio.create_task(player.start(), name="taste-lab-player")
    print("Observing playback. Ctrl+C stops. No playback commands will be sent.")
    try:
        while True:
            done, _ = await asyncio.wait({runner}, timeout=1)
            if done:
                await runner
                return

            sample = _sample(player.state) if player.is_ready else None
            event = observer.observe(sample, clock=time.monotonic(), at=time.time())
            if event is not None:
                await asyncio.to_thread(store.record, event)
                print(f"Recorded {event.kind} (confidence {event.confidence:.2f})")
    finally:
        try:
            event = observer.finish(time.time())
            if event is not None:
                await asyncio.to_thread(store.record, event)
        finally:
            try:
                await player.close()
            finally:
                runner.cancel()
                await asyncio.gather(runner, return_exceptions=True)


async def _online(args: argparse.Namespace, store: Store) -> None:
    cookie = os.environ.get("SPOTIFY_COOKIE", "").strip()
    if args.env_file is not None:
        try:
            from dotenv import dotenv_values
        except ImportError as error:
            raise RuntimeError("Install python-dotenv to read --env-file") from error

        if not args.env_file.is_file():
            raise ValueError("The requested environment file does not exist")
        cookie = cookie or (dotenv_values(args.env_file).get("SPOTIFY_COOKIE") or "").strip()

    if not cookie:
        raise ValueError("Set SPOTIFY_COOKIE in this process environment")

    async with await AsyncClient.from_cookies(cookie) as client:
        if args.command == "observe":
            await observe(Player(client), store)
            return

        async with Catalogue(client) as catalogue:
            if args.command == "sync":
                result = await sync_library(catalogue, client.session, store, print)
                print(json.dumps(asdict(result), indent=2))
                if result.failures:
                    raise RuntimeError(
                        "Some sources could not be imported; previous data was retained"
                    )
                return

            snapshot = await asyncio.to_thread(store.snapshot)
            if not snapshot.seeds:
                raise ValueError("Run sync before retrieving candidates")

            seeds = training_seeds(snapshot, time.time())
            held = ()
            if args.command == "evaluate":
                seeds, held = split_by_artist(seeds)
                if not seeds or not held:
                    raise ValueError("The library needs more distinct artists for this evaluation")

            candidates, failures = await retrieve(
                catalogue,
                seeds,
                seed_artists=args.seed_artists,
                neighbors=args.neighbors,
            )
            if failures:
                print(json.dumps({"retrieval_failures": failures}))
            if not candidates:
                raise RuntimeError("No candidates were retrieved; the previous pool was retained")

            if args.command == "evaluate":
                benchmark = Benchmark(seeds, held, candidates)
                await asyncio.to_thread(store.save_benchmark, benchmark)
                await _evaluate(store, benchmark)
            else:
                if failures:
                    merged = {candidate.song.uri: candidate for candidate in snapshot.candidates}
                    merged.update({candidate.song.uri: candidate for candidate in candidates})
                    candidates = tuple(merged.values())
                await asyncio.to_thread(store.replace_candidates, candidates)
                print(f"Cached {len(candidates)} unique candidate tracks")


async def _evaluate(store: Store, benchmark: Benchmark) -> None:
    features = await asyncio.to_thread(store.audio_features)
    result = compare(benchmark.train, benchmark.held, benchmark.candidates, features=features)
    print(
        json.dumps(
            {
                **asdict(result),
                "retrieval_recall": result.retrieval_recall,
                "ranking_recall": result.ranking_recall,
            },
            indent=2,
        )
    )
    print("This measures recovery of withheld library tracks, not enjoyment of unknown songs.")


async def run(args: argparse.Namespace) -> None:
    store = await asyncio.to_thread(Store, args.db)
    if args.command == "evaluate" and args.cached:
        await _evaluate(store, await asyncio.to_thread(store.benchmark))
        return
    if args.command in {"sync", "refresh", "observe", "evaluate"}:
        await _online(args, store)
        return

    snapshot = await asyncio.to_thread(store.snapshot)
    if args.command == "enrich":
        from .youtube import enrich

        counts = await asyncio.to_thread(enrich, store, limit=args.limit, force=args.force)
        print(json.dumps(counts, indent=2))
        if not counts["analyzed"] and not counts["cached"]:
            raise RuntimeError("No audio was analyzed; metadata ranking remains available")
        return

    if args.command == "audio-import":
        from .extract import import_audio

        imported, reused = await asyncio.to_thread(import_audio, store, args.manifest)
        print(f"Analyzed {imported} recordings; reused {reused} unchanged recordings")
        return

    if args.command == "status":
        print(
            json.dumps(
                {
                    "seed_records": len(snapshot.seeds),
                    "candidate_tracks": len(snapshot.candidates),
                    "feedback_events": len(snapshot.feedback),
                    "shown_tracks": len(snapshot.impressions),
                    "analyzed_recordings": len(await asyncio.to_thread(store.audio_features)),
                },
                indent=2,
            )
        )
        return

    if args.command == "feedback":
        uri = parse_spotify_resource(args.track, "track").uri
        known = {seed.song.uri for seed in snapshot.seeds} | {
            item.song.uri for item in snapshot.candidates
        }
        if uri not in known:
            raise ValueError("Import or retrieve this track first so feedback has artist context")
        kind: FeedbackKind = "early_transition" if args.kind == "skip" else args.kind
        await asyncio.to_thread(store.record, Feedback(str(uuid4()), uri, kind, time.time()))
        print("Recorded locally. Your Spotify library was not changed.")
        return

    policy = Policy(novelty=args.novelty, cooldown_hours=args.cooldown_hours)
    now = time.time()
    features = () if args.metadata_only else await asyncio.to_thread(store.audio_features)
    audio = audio_taste(snapshot, features, now) if features else None
    results = recommend(snapshot, now=now, limit=args.limit, policy=policy, audio=audio)
    if args.json:
        print(json.dumps([asdict(result) for result in results], indent=2))
    else:
        for index, result in enumerate(results, 1):
            print(f"{index}. {result.song.name} — {', '.join(result.song.artist_names)}")
            print(f"   {result.song.url}")
            print("   " + "; ".join(result.reasons))
        if not results:
            print("No eligible discoveries. Run sync/refresh or try a shorter cooldown.")

    if not args.dry_run:
        await asyncio.to_thread(store.shown, [result.song for result in results], time.time())


def main() -> int:
    args = _parser().parse_args()
    try:
        asyncio.run(run(args))
    except KeyboardInterrupt:
        return 130
    except (SpotAPIError, ValueError, RuntimeError, OSError) as error:
        print(f"taste-lab: {error}")
        return 1
    except ExceptionGroup:
        print(
            "taste-lab: grouped retrieval or connection failure; retry after checking the session"
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
