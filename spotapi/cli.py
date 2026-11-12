"""Search Spotify, manage your library, and control an existing player."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from collections.abc import Sequence
from contextlib import aclosing
from dataclasses import asdict, is_dataclass

from .account import Private
from .library import LikedTracks
from .models import PlaylistEntry
from .operations import SEARCH_DESKTOP_SECTIONS, SearchKind
from .player import Player
from .playlist import Playlist
from .public import Public
from .types import SpotAPIError


def _limit(value: str) -> int:
    number = int(value)
    if not 1 <= number <= 50:
        raise argparse.ArgumentTypeError("choose a number from 1 to 50")
    return number


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spotapi", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="search the public catalogue")
    search.add_argument("query", help="text to search for")
    search.add_argument("--type", choices=tuple(SEARCH_DESKTOP_SECTIONS), default="track")
    search.add_argument("--limit", type=_limit, default=10)
    search.add_argument("--json", action="store_true", help="print results as JSON")
    get = commands.add_parser("get", help="look up a Spotify URL or URI as JSON")
    get.add_argument("resource", help="Spotify URL or URI")
    credits = commands.add_parser("credits", help="show a track's contributors as JSON")
    credits.add_argument("track")

    playlist = commands.add_parser("playlist", help="list or edit playlist occurrences")
    playlists = playlist.add_subparsers(dest="action", required=True)
    items = playlists.add_parser("items", help="list occurrences with their IDs")
    items.add_argument("playlist")
    items.add_argument("--limit", type=_limit, default=20)
    items.add_argument("--private", action="store_true", help="use your Spotify session")
    for action, label, value in (
        ("add", "append tracks", "tracks"),
        ("remove", "remove exact occurrence IDs", "uids"),
        ("move", "move exact occurrence IDs", "uids"),
    ):
        edit = playlists.add_parser(action, help=label)
        edit.add_argument("playlist")
        edit.add_argument(value, nargs="+")
        if action == "move":
            position = edit.add_mutually_exclusive_group()
            position.add_argument("--before", metavar="UID")
            position.add_argument("--after", metavar="UID")

    library = commands.add_parser("library", help="read or change saved tracks")
    saved = library.add_subparsers(dest="action", required=True)
    saved.add_parser("list", help="list liked tracks").add_argument(
        "--limit", type=_limit, default=20
    )
    for action, label in (
        ("contains", "check whether tracks are liked"),
        ("add", "like tracks"),
        ("remove", "unlike tracks"),
    ):
        saved.add_parser(action, help=label).add_argument("tracks", nargs="+")

    player = commands.add_parser("player", help="control an existing Spotify device")
    playback = player.add_subparsers(dest="action", required=True)
    for action in ("status", "pause", "resume", "next", "previous"):
        playback.add_parser(action, help=f"{action} on the active device")
    playback.add_parser("play", help="play a Spotify resource").add_argument("resource")
    playback.add_parser("seek", help="seek to a position in milliseconds").add_argument(
        "milliseconds", type=int
    )
    playback.add_parser("volume", help="set volume from 0 to 100").add_argument(
        "percent", type=int
    )
    playback.add_parser("queue", help="add a track to the queue").add_argument("track")
    return parser


def _json(value: object) -> None:
    def encode(item: object) -> object:
        return asdict(item) if is_dataclass(item) and not isinstance(item, type) else str(item)

    print(json.dumps(value, indent=2, default=encode))


async def _search(args: argparse.Namespace) -> None:
    kind: SearchKind = args.type
    results = await Public.search(args.query, types=kind, limit=args.limit)
    hits = results[kind]
    if args.json:
        _json(hits)
        return

    for hit in hits:
        print(f"{hit.name}\t{hit.uri}")
    if not hits:
        print(f"No {kind}s found.", file=sys.stderr)


async def _run_library(liked: LikedTracks, args: argparse.Namespace) -> None:
    action: str = args.action
    if action == "list":
        _json(await liked.get(limit=args.limit))
    elif action == "contains":
        flags = await liked.contains(args.tracks)
        _json(
            [
                {"track": track, "liked": flag}
                for track, flag in zip(args.tracks, flags, strict=True)
            ]
        )
    elif action == "add":
        await liked.add(args.tracks)
    else:
        await liked.remove(args.tracks)


async def _run_playlist(playlist: Playlist, args: argparse.Namespace) -> None:
    action: str = args.action
    if action == "items":
        items: list[PlaylistEntry] = []
        async with aclosing(playlist.items(limit=args.limit)) as entries:
            async for entry in entries:
                items.append(entry)
                if len(items) == args.limit:
                    break
        _json(items)
    elif action == "add":
        await playlist.add_tracks(*args.tracks)
    elif action == "remove":
        await playlist.remove_occurrences(*args.uids)
    else:
        await playlist.move_occurrences(*args.uids, before=args.before, after=args.after)


async def _run_player(player: Player, args: argparse.Namespace) -> None:
    action: str = args.action
    if action == "status":
        _json({"state": player.state, "devices": player.devices})
    elif action == "play":
        await player.play(args.resource)
    elif action == "seek":
        await player.seek(args.milliseconds)
    elif action == "volume":
        await player.volume(args.percent)
    elif action == "queue":
        await player.add_to_queue(args.track)
    else:
        await {
            "pause": player.pause,
            "resume": player.resume,
            "next": player.next,
            "previous": player.previous,
        }[action]()


async def _run(args: argparse.Namespace) -> None:
    command: str = args.command
    if command == "search":
        await _search(args)
        return
    if command == "get":
        _json(await Public.get(args.resource))
        return
    if command == "credits":
        _json(await Public.get_track_credits(args.track))
        return
    if command == "playlist" and args.action == "items" and not args.private:
        async with aclosing(Public.get_playlist_items(args.playlist, limit=args.limit)) as pages:
            _json((await anext(pages, ()))[: args.limit])
        return

    cookie = os.environ.get("SPOTIFY_COOKIE", "").strip()
    if not cookie:
        raise ValueError("Set SPOTIFY_COOKIE to use your Spotify account.")

    async with Private.from_cookies(cookie) as account:
        if command == "library":
            await _run_library(account.liked_tracks, args)
        elif command == "playlist":
            await _run_playlist(Playlist(account.session, args.playlist), args)
        else:
            async with Player(account.session).connect() as player:
                await _run_player(player, args)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the requested command and return a process exit code."""
    args = _parser().parse_args(argv)
    try:
        asyncio.run(_run(args))
    except (SpotAPIError, ValueError, RuntimeError, TimeoutError) as error:
        print(f"spotapi: {str(error) or 'Request timed out.'}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    return 0
