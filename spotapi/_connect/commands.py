"""Parse human-sized player commands without mixing syntax with Spotify I/O."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass

_COMMANDS = frozenset(
    {
        "help",
        "devices",
        "use",
        "transfer",
        "pause",
        "resume",
        "toggle",
        "next",
        "previous",
        "seek",
        "volume",
        "shuffle",
        "repeat",
        "search",
        "play",
        "queue",
        "refresh",
        "clear",
        "quit",
    }
)
_ALIASES = {
    "prev": "previous",
    "cls": "clear",
    "exit": "quit",
    "exit()": "quit",
    "quit()": "quit",
    "q": "quit",
    "?": "help",
}
_PROFILE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,39}\Z")


@dataclass(frozen=True, slots=True)
class Command:
    """A validated command and its uninterpreted Spotify/search argument."""

    action: str
    argument: str = ""


def profile_name(value: str) -> str:
    """Keep keyring account labels short, explicit and filename-independent."""
    if not _PROFILE.fullmatch(value):
        raise ValueError("Profile must be 1-40 letters, numbers, dots, dashes or underscores")
    return value


def duration_ms(value: str) -> int:
    """Parse a seek offset, e.g. 1:30 or 01:02:03, as milliseconds."""
    parts = value.split(":")
    if not 1 <= len(parts) <= 3 or any(
        not part.isascii() or not part.isdecimal() for part in parts
    ):
        raise ValueError("Seek to seconds, mm:ss or hh:mm:ss (e.g. seek 1:30)")
    numbers = [int(part) for part in parts]
    if len(numbers) > 1 and any(n >= 60 for n in numbers[1:]):
        raise ValueError("Minutes/seconds after the first field must be less than 60")
    seconds = 0
    for number in numbers:
        seconds = seconds * 60 + number
    if seconds > 24 * 60 * 60:
        raise ValueError("Seek position must be 24 hours or less")
    return seconds * 1_000


def parse_command(source: str) -> Command:
    """Accept either slash commands or plain words; reject unknown arguments."""
    value = source.strip().removeprefix("/")
    if not value:
        raise ValueError("Type /help to see available commands")
    try:
        parts = shlex.split(value)
    except ValueError as exc:
        raise ValueError("Unclosed quote in command") from exc
    if not parts:
        raise ValueError("Type /help to see available commands")

    action = _ALIASES.get(parts[0].lower(), parts[0].lower())
    if action not in _COMMANDS:
        raise ValueError(f"Unknown command: {parts[0]}. Type /help")

    needs_value = {
        "use",
        "transfer",
        "seek",
        "volume",
        "shuffle",
        "repeat",
        "search",
        "play",
        "queue",
    }
    if action in needs_value and len(parts) < 2:
        raise ValueError(f"Usage: {action} <value>")
    if action not in needs_value and len(parts) > 1:
        raise ValueError(f"{action} does not take any arguments")
    if action in {"use", "transfer", "seek", "volume", "shuffle", "repeat"} and len(parts) != 2:
        raise ValueError(f"Usage: {action} <value>")

    argument = " ".join(parts[1:])
    match action:
        case "seek":
            duration_ms(argument)
        case "use" | "transfer":
            if not argument.isascii() or not argument.isdecimal() or int(argument) < 1:
                raise ValueError("Choose a device number from /devices")
        case "volume":
            if not argument.isascii() or not argument.isdecimal() or not 0 <= int(argument) <= 100:
                raise ValueError("Volume must be 0-100")
        case "shuffle" if argument not in {"on", "off"}:
            raise ValueError("Shuffle must be on or off")
        case "repeat" if argument not in {"off", "track", "context"}:
            raise ValueError("Repeat must be off, track or context")
        case _:
            pass  # Valid commands without additional validation.
    return Command(action, argument)
