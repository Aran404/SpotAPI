"""Search Spotify, manage your library, and control an existing player."""

from __future__ import annotations

import argparse
import asyncio
import difflib
import importlib
import importlib.util
import json
import os
import sys
from collections.abc import AsyncGenerator, Awaitable, Callable, Sequence
from contextlib import aclosing, asynccontextmanager
from importlib.metadata import version as package_version
from typing import NoReturn, cast

from .account import Private
from .embeds import get_embed
from .library import LikedTracks
from .login import SavedSession
from .media import Media
from .models import Album, PlaylistEntry, Track
from .operations import SEARCH_DESKTOP_SECTIONS, SearchKind
from .player import Player
from .playlist import Playlist
from .public import Public
from .serialization import to_dict
from .types import BaseClientError, SpotAPIError

# CLI presentation is kept here rather than introducing a dependency on Rich or
# Textual for commands that only need the base installation.
_COMMAND_GROUPS: tuple[tuple[str, tuple[tuple[str, str], ...]], ...] = (
    (
        "Start here",
        (
            ("connect", "Live terminal controller"),
            ("discover", "Interactive music browser"),
            ("studio", "Desktop workbench"),
        ),
    ),
    (
        "Explore",
        (
            ("search", "Search tracks, albums, artists"),
            ("get", "Look up a Spotify URL or URI"),
            ("credits", "Track credits"),
            ("lyrics", "Lyrics (account required)"),
            ("transcript", "Episode transcripts"),
        ),
    ),
    (
        "Your Spotify",
        (
            ("player", "Control an existing player"),
            ("library", "Manage liked tracks"),
            ("playlist", "Manage playlist entries"),
        ),
    ),
    (
        "More tools",
        (
            ("charts", "Browse charts"),
            ("chart", "Chart details"),
            ("events", "Artist events"),
            ("similar-albums", "Album recommendations"),
            ("colors", "Artwork colors"),
            ("embed", "Embed metadata"),
            ("download", "Download published assets"),
        ),
    ),
)
_ALL_COMMANDS = tuple(name for _, entries in _COMMAND_GROUPS for name, _ in entries)


def _subcommands(parser: argparse.ArgumentParser) -> dict[str, argparse.ArgumentParser]:
    """Find child parsers via the public Action.choices interface."""
    children: dict[str, argparse.ArgumentParser] = {}
    for action in parser._actions:
        choices: object = action.choices
        if not isinstance(choices, dict):
            continue
        for name, child in cast("dict[object, object]", choices).items():
            if isinstance(name, str) and isinstance(child, argparse.ArgumentParser):
                children[name] = child
    return children


class _CommandParser(argparse.ArgumentParser):
    """Compact errors with guidance, without changing argparse's exit codes."""

    def error(self, message: str) -> NoReturn:
        if "invalid choice:" in message and (
            message.startswith("argument command:") or message.startswith("argument action:")
        ):
            invalid = message.partition("invalid choice: ")[2].split(" (choose from", 1)[0]
            command = invalid.strip().strip("'\"")
            choices = tuple(_subcommands(self)) or _ALL_COMMANDS
            candidate = difflib.get_close_matches(command, choices, n=1, cutoff=0.6)
            if candidate:
                message = f"Unknown command {command!r}. Did you mean {candidate[0]!r}?"
            elif command and not command.startswith("-"):
                message = f"Unknown command {command!r}."
        self.exit(2, f"spotapi: {message}\nRun 'spotapi --help' to see available commands.\n")


class _RootParser(_CommandParser):
    """Show a short grouped landing page rather than argparse's huge choice list."""

    def format_help(self) -> str:
        lines = [
            "SpotAPI — explore Spotify and control your existing player",
            "",
            "Usage: spotapi <command> [options]",
            "",
        ]
        for heading, commands in _COMMAND_GROUPS:
            lines.append(heading)
            lines.extend(f"  {name:<17} {description}" for name, description in commands)
            lines.append("")
        lines.extend(
            (
                "Examples",
                "  spotapi connect                 Interactive player terminal",
                "  spotapi search 'Daft Punk'     Search the catalogue",
                "  spotapi player pause           Pause the current player",
                "  spotapi get <spotify-url>      Inspect a resource",
                "",
                "Run 'spotapi <command> --help' for command-specific options.",
                "Use --json after a command for machine-readable output.",
                "Default output remains JSON when redirected or piped.",
                "",
            )
        )
        return "\n".join(lines)


def _add_output_options(parser: argparse.ArgumentParser) -> None:
    """Offer --json after every leaf command, including nested player actions."""
    children = _subcommands(parser)
    if children:
        for child in children.values():
            _add_output_options(child)
        return
    if parser.prog.split()[-1] in {"studio", "discover", "connect"}:
        return
    if not any("--json" in action.option_strings for action in parser._actions):
        parser.add_argument("--json", action="store_true", help="output raw JSON for scripts")


def _human(value: object) -> str:
    """Simple lossless hierarchy for a terminal, with no external UI package."""
    data: object = to_dict(value)
    lines: list[str] = []

    def visit(item: object, depth: int = 0, label: str = "") -> None:
        indent = "  " * depth
        if isinstance(item, dict):
            entries = cast("dict[str, object]", item)
            if label:
                lines.append(f"{indent}{label}:")
                depth += 1
            if not entries:
                lines.append("  " * depth + "(empty)")
            for key, subvalue in entries.items():
                visit(subvalue, depth, key.replace("_", " "))
        elif isinstance(item, list):
            entries = cast("list[object]", item)
            if label:
                lines.append(f"{indent}{label} ({len(entries)}):")
                depth += 1
            if not entries:
                lines.append("  " * depth + "(none)")
            for number, entry in enumerate(entries, 1):
                if isinstance(entry, dict):
                    fields = cast("dict[str, object]", entry)
                    title = fields.get("name") or fields.get("title") or fields.get("uri")
                    lines.append("  " * depth + f"{number}. {title or 'Item'}")
                    for key, subvalue in fields.items():
                        if title is not None and key in {"name", "title"}:
                            continue
                        visit(subvalue, depth + 1, key.replace("_", " "))
                else:
                    visit(entry, depth, str(number))
        else:
            text = "—" if item is None else str(item)
            lines.append(f"{indent}{label}: {text}" if label else f"{indent}{text}")

    visit(data)
    return "\n".join(lines)


def _display(value: object, args: argparse.Namespace) -> None:
    if getattr(args, "json", False) or not sys.stdout.isatty():
        _json(value)
    else:
        print(_human(value))


def _acknowledge(message: str) -> None:
    # Machine-oriented commands previously produced no output upon mutation.
    if sys.stdout.isatty():
        print(message)


def _limit(value: str, *, maximum: int = 50) -> int:
    number = int(value)
    if not 1 <= number <= maximum:
        raise argparse.ArgumentTypeError(f"choose a number from 1 to {maximum}")

    return number


def _position(value: str) -> int:
    milliseconds = int(value)
    if milliseconds < 0:
        raise argparse.ArgumentTypeError("choose a nonnegative position in milliseconds")

    return milliseconds


def _volume(value: str) -> int:
    percent = int(value)
    if not 0 <= percent <= 100:
        raise argparse.ArgumentTypeError("choose a percentage from 0 to 100")

    return percent


def _parser() -> argparse.ArgumentParser:
    parser = _RootParser(prog="spotapi", description=__doc__, add_help=False)
    parser.add_argument("-h", "--help", action="help", help="show this help message")
    parser.set_defaults(resource_lookup=None)
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {package_version('spotapi')}",
    )
    commands = parser.add_subparsers(
        dest="command", required=True, metavar="<command>", parser_class=_CommandParser
    )
    commands.add_parser("studio", help="open the desktop application (studio extra)")
    connect = commands.add_parser(
        "connect", help="interactive, persistent Spotify Connect terminal"
    )
    connect.add_argument(
        "--profile",
        default="default",
        metavar="NAME",
        help="saved OS-keyring account (default: default)",
    )
    connect.add_argument(
        "--force",
        action="store_true",
        help="open a fresh login window and replace this saved account",
    )
    discover = commands.add_parser("discover", help="browse Spotify in your terminal (demo extra)")
    discover.add_argument("query", nargs="*", help="search words or a Spotify link")
    search = commands.add_parser("search", help="search the public catalogue")
    search.add_argument("query", help="text to search for")
    search.add_argument("--type", choices=tuple(SEARCH_DESKTOP_SECTIONS), default="track")
    search.add_argument("--limit", type=lambda value: _limit(value, maximum=100), default=10)
    search.add_argument("--language", help="Spotify language or locale, such as fr-CA")
    get = commands.add_parser("get", help="look up a Spotify URL or URI as JSON")
    get.add_argument("resource", help="Spotify URL or URI")
    credits = commands.add_parser("credits", help="show a track's contributors as JSON")
    credits.add_argument("track")

    for name, help_text, lookup in (
        ("chart", "read editorial chart metadata", Public.get_chart),
        ("events", "read upcoming artist concerts", Public.get_artist_events),
        ("similar-albums", "recommend albums from a track", Public.get_similar_albums),
        ("colors", "extract a Spotify image palette", Public.get_colors),
        ("embed", "read public embed metadata and preview URLs", get_embed),
    ):
        subcommand = commands.add_parser(name, help=help_text)
        subcommand.add_argument("resource")
        subcommand.set_defaults(resource_lookup=lookup)

    for name, help_text in (
        ("transcript", "read episode captions using SPOTIFY_COOKIE"),
        ("lyrics", "read entitled lyrics using SPOTIFY_COOKIE"),
    ):
        commands.add_parser(name, help=help_text).add_argument("resource")
    commands.add_parser("charts", help="list editorial chart shortcuts")
    _configure_download(
        commands.add_parser("download", help="save published preview, cover or Canvas assets")
    )
    _configure_playlist(commands.add_parser("playlist", help="list or edit playlist occurrences"))
    _configure_library(commands.add_parser("library", help="read or change saved tracks"))
    _configure_player(commands.add_parser("player", help="control an existing Spotify device"))

    _add_output_options(parser)
    # The same named OS-keyring profiles used by Connect work in CLI commands.
    # Put --profile on leaves so it works after a positional action or resource.
    for name in ("library", "playlist", "player"):
        for child in _subcommands(_subcommands(parser)[name]).values():
            child.add_argument(
                "--profile",
                metavar="NAME",
                help="saved Connect profile; overrides SPOTIFY_COOKIE",
            )
    for name in ("lyrics", "transcript"):
        _subcommands(parser)[name].add_argument(
            "--profile",
            metavar="NAME",
            help="saved Connect profile; overrides SPOTIFY_COOKIE",
        )
    return parser


def _configure_download(download: argparse.ArgumentParser) -> None:
    download.add_argument("kind", choices=("cover", "preview", "canvas"))
    download.add_argument("resource", help="Spotify resource URL or URI")
    download.add_argument(
        "--output", required=True, help="Destination file; existing files are never replaced"
    )

    download.add_argument(
        "--embed-cover",
        action="store_true",
        help="Tag a preview with artwork; requires spotapi[media]",
    )


def _configure_playlist(playlist: argparse.ArgumentParser) -> None:
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


def _configure_library(library: argparse.ArgumentParser) -> None:
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


def _configure_player(player: argparse.ArgumentParser) -> None:
    playback = player.add_subparsers(dest="action", required=True)
    for action in ("status", "pause", "resume", "next", "previous"):
        playback.add_parser(action, help=f"{action} on the active device")
    playback.add_parser("play", help="play a Spotify resource").add_argument("resource")
    playback.add_parser("seek", help="seek to a position in milliseconds").add_argument(
        "milliseconds", type=_position
    )
    playback.add_parser("volume", help="set volume from 0 to 100").add_argument(
        "percent", type=_volume
    )
    playback.add_parser("queue", help="add a track to the queue").add_argument("track")


def _json(value: object) -> None:
    print(json.dumps(to_dict(value), indent=2))


async def _search(args: argparse.Namespace) -> None:
    kind: SearchKind = args.type
    if not args.json and sys.stderr.isatty():
        print("Searching Spotify...", file=sys.stderr)

    results = await Public.search(args.query, types=kind, limit=args.limit, language=args.language)
    hits = results[kind]
    if args.json:
        _display(hits, args)
        return

    for hit in hits:
        names = ""
        if isinstance(hit, (Track, Album)):
            artists = hit.artists.items if hit.artists else ()
            names = ", ".join(artist.profile.name for artist in artists if artist.profile)
        print(f"{hit.name} — {names}" if names else hit.name)
        print(f"  {hit.uri}")
    if not hits:
        print(f"No {kind}s found.", file=sys.stderr)


async def _run_library(liked: LikedTracks, args: argparse.Namespace) -> None:
    action: str = args.action
    match action:
        case "list":
            _display(await liked.get(limit=args.limit), args)
        case "contains":
            flags = await liked.contains(args.tracks)
            _display(
                [
                    {"track": track, "liked": flag}
                    for track, flag in zip(args.tracks, flags, strict=True)
                ],
                args,
            )
        case "add":
            await liked.add(args.tracks)
            _acknowledge(f"Added {len(args.tracks)} track(s) to your library (request completed).")
        case "remove":
            await liked.remove(args.tracks)
            _acknowledge(
                f"Removed {len(args.tracks)} track(s) from your library (request completed)."
            )
        case _:
            raise ValueError(f"Unsupported library action: {action}")


async def _run_playlist(playlist: Playlist, args: argparse.Namespace) -> None:
    action: str = args.action
    match action:
        case "items":
            items: list[PlaylistEntry] = []
            async with aclosing(playlist.items(limit=args.limit)) as entries:
                async for entry in entries:
                    items.append(entry)
                    if len(items) == args.limit:
                        break
            _display(items, args)
        case "add":
            await playlist.add_tracks(*args.tracks)
            _acknowledge(f"Added {len(args.tracks)} track(s) to the playlist.")
        case "remove":
            await playlist.remove_occurrences(*args.uids)
            _acknowledge(f"Removed {len(args.uids)} playlist occurrence(s).")
        case "move":
            await playlist.move_occurrences(*args.uids, before=args.before, after=args.after)
            _acknowledge(f"Move requested for {len(args.uids)} playlist occurrence(s).")
        case _:
            raise ValueError(f"Unsupported playlist action: {action}")


async def _run_player(player: Player, args: argparse.Namespace) -> None:
    action: str = args.action
    match action:
        case "status":
            _display({"state": player.state, "devices": player.devices}, args)
        case "play":
            await player.play(args.resource)
        case "seek":
            await player.seek(args.milliseconds)
        case "volume":
            await player.volume(args.percent)
        case "queue":
            await player.add_to_queue(args.track)
        case "pause":
            await player.pause()
        case "resume":
            await player.resume()
        case "next":
            await player.next()
        case "previous":
            await player.previous()
        case _:
            raise ValueError(f"Unsupported player action: {action}")
    if action != "status":
        _acknowledge(
            f"{action.capitalize()} request completed; confirm playback state on Spotify."
        )


async def _run_download(args: argparse.Namespace) -> None:
    media = Media()
    if args.kind == "canvas":
        canvas = await Public.get_canvas(args.resource)
        if canvas is None:
            raise ValueError("This track has no Canvas")
        destination = await media.download_canvas(canvas, args.output)
    else:
        source = await get_embed(args.resource)
        if args.kind == "cover":
            destination = await media.download_cover(source, args.output)
        else:
            destination = await media.download_preview(
                source, args.output, embed_cover=args.embed_cover
            )
    if getattr(args, "json", False) or not sys.stdout.isatty():
        _json({"path": str(destination)})
    else:
        print(f"Saved to {destination}")


@asynccontextmanager
async def _authenticated_account(args: argparse.Namespace) -> AsyncGenerator[Private, None]:
    """Borrow a named Connect profile or an explicit environment session.

    A caller's SPOTIFY_COOKIE wins by default. Supplying --profile explicitly
    selects the saved OS-keyring profile instead; no browser is launched and
    no credentials are written to disk by this command.
    """
    profile: str | None = getattr(args, "profile", None)
    cookie = os.environ.get("SPOTIFY_COOKIE", "").strip() if profile is None else ""
    if cookie:
        async with Private.from_cookies(cookie) as account:
            yield account
        return

    # Keep the base install free of keyring dependencies and provide a useful
    # first-use message instead of an ImportError or a credential-store traceback.
    if importlib.util.find_spec("keyring") is None:
        raise ValueError(
            "This command needs a Spotify session. Set SPOTIFY_COOKIE, or install "
            "'spotapi[connect]' and run 'spotapi connect' to save a profile."
        )

    from ._connect.commands import profile_name

    name = profile_name(profile or "default")
    # The keyring Python package may be installed without a usable OS backend,
    # especially on headless Linux hosts. Keep the CLI recovery actionable.
    keyring_errors = importlib.import_module("keyring.errors")
    try:
        client = await SavedSession(name).open()
    except keyring_errors.NoKeyringError as error:
        raise ValueError(
            "No supported OS keyring backend is available. Set SPOTIFY_COOKIE "
            "or configure a supported secure keyring backend."
        ) from error
    except BaseClientError as error:
        raise ValueError(
            f"No saved Spotify profile {name!r}. Set SPOTIFY_COOKIE, or run "
            "'spotapi connect' to sign in and save this profile."
        ) from error

    async with client:
        yield Private(client)


async def _run(args: argparse.Namespace) -> None:
    command: str = args.command
    resource_lookup: Callable[[str], Awaitable[object]] | None = args.resource_lookup

    if resource_lookup is not None:
        _display(await resource_lookup(args.resource), args)
        return

    if command == "charts":
        _display(Public.list_charts(), args)
        return

    if command == "download":
        await _run_download(args)
        return
    if command == "search":
        await _search(args)
        return
    if command == "get":
        _display(await Public.get(args.resource), args)
        return
    if command == "credits":
        _display(await Public.get_track_credits(args.track), args)
        return
    if command == "playlist" and args.action == "items" and not args.private:
        async with aclosing(Public.get_playlist_items(args.playlist, limit=args.limit)) as pages:
            _display((await anext(pages, ()))[: args.limit], args)
        return

    async with _authenticated_account(args) as account:
        if command in {"transcript", "lyrics"}:
            helper = account.transcripts if command == "transcript" else account.lyrics
            _display(await helper.get(args.resource), args)
        elif command == "library":
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
        match args.command:
            case "studio":
                if any(importlib.util.find_spec(name) is None for name in ("webview", "dotenv")):
                    raise RuntimeError('Install Studio with: pip install "spotapi[studio]"')
                desktop = importlib.import_module("spotapi._studio.desktop")
                desktop.main()
            case "connect":
                if importlib.util.find_spec("textual") is None:
                    raise RuntimeError(
                        'Connect requires its optional interface. Install with: python -m pip install -e ".[connect]" (from the repository), or python -m pip install "spotapi[connect]"'
                    )
                from ._connect.commands import profile_name

                profile_name(args.profile)
                controller = importlib.import_module("spotapi._connect.app")
                asyncio.run(controller.run_connect(args.profile, force=args.force))
            case "discover":
                dependencies = ("textual", "textual_image", "PIL", "httpx")
                if any(importlib.util.find_spec(name) is None for name in dependencies):
                    raise RuntimeError(
                        'Install the terminal browser with: pip install "spotapi[demo]"'
                    )
                browser = importlib.import_module("spotapi._demo.discover")
                browser.main(" ".join(args.query))
            case _:
                asyncio.run(_run(args))
    except (SpotAPIError, ValueError, RuntimeError, TimeoutError, OSError) as error:
        print(f"spotapi: {str(error) or 'Request timed out.'}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    return 0
