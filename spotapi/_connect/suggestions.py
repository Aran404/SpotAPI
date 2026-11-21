"""Small, typed command catalogue shared by completion and help.

Suggestions are descriptions, not executable shell commands. Choosing an entry
fills the composer; only explicitly submitting it executes a Spotify mutation.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Hint:
    example: str
    description: str


HINTS: tuple[Hint, ...] = (
    Hint("pause", "Pause the active player"),
    Hint("resume", "Resume playback"),
    Hint("toggle", "Pause or resume"),
    Hint("next", "Skip to the next track"),
    Hint("previous", "Go to the previous track"),
    Hint("seek 1:30", "Jump to a playback position"),
    Hint("volume 60", "Change player volume (0–100)"),
    Hint("shuffle on", "Enable shuffle"),
    Hint("shuffle off", "Disable shuffle"),
    Hint("repeat track", "Repeat this track"),
    Hint("repeat context", "Repeat the album or playlist"),
    Hint("repeat off", "Disable repeat"),
    Hint("search Daft Punk", "Find tracks without leaving Connect"),
    Hint("play 1", "Play a track from search results"),
    Hint("queue 1", "Queue a track from search results"),
    Hint("devices", "List available Spotify players"),
    Hint("use 1", "Target a device (without transferring)"),
    Hint("transfer 1", "Move playback to a device"),
    Hint("refresh", "Request the latest Spotify state"),
    Hint("clear", "Clear activity and diagnostic logs (cls)"),
    Hint("help", "Show all commands and keyboard shortcuts"),
    Hint("exit", "Close the Connect session (exit(), quit)"),
)


def completions(source: str, *, limit: int = 6) -> tuple[Hint, ...]:
    """Match slash or plain commands, prioritizing prefix matches."""
    query = source.strip().removeprefix("/").casefold()
    if not query:
        return HINTS[:limit]
    starts = [hint for hint in HINTS if hint.example.casefold().startswith(query)]
    contains = [hint for hint in HINTS if query in hint.example.casefold() and hint not in starts]
    return tuple((starts + contains)[:limit])
