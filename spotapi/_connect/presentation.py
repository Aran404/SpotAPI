"""Pure, bounded display helpers for the Connect terminal."""

from __future__ import annotations

from dataclasses import dataclass

from rich.cells import cell_len, set_cell_size

from spotapi.models import PlaybackTrack
from spotapi.models.catalogue.track import Track
from spotapi.models.playback import Device


def clock(milliseconds: int) -> str:
    """Format nonnegative playback milliseconds as m:ss or h:mm:ss."""
    seconds = max(0, milliseconds // 1_000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02}:{seconds:02}"
    return f"{minutes}:{seconds:02}"


def progress_bar(fraction: float, *, width: int = 28) -> str:
    """Draw an ASCII-safe meter without Unicode/terminal width surprises."""
    count = max(0, min(width, round(fraction * width)))
    return "━" * count + "─" * (width - count)


def queue_rows(tracks: tuple[PlaybackTrack, ...], *, limit: int = 4) -> str:
    """Show only Spotify-reported queue entries, with no invented placeholders."""
    if not tracks:
        return "No upcoming tracks reported by Spotify."
    rows: list[str] = []
    for index, track in enumerate(tracks[:limit], 1):
        name = track.name or track.uri.rsplit(":", 1)[-1]
        artist = f"  ·  {track.artist}" if track.artist else ""
        rows.append(f"{index:>2}  {name}{artist}")
    if len(tracks) > limit:
        rows.append(f"    +{len(tracks) - limit} more reported")
    return "\n".join(rows)


@dataclass(frozen=True, slots=True)
class Identity:
    """Public display name and internal account ID are different concepts."""

    username: str | None = None
    display_name: str | None = None

    @property
    def label(self) -> str:
        return self.display_name or ("Signed in" if self.username else "Connecting account")

    @property
    def prompt(self) -> str:
        """Prefer the stable Spotify username over the optional display name.

        Both derive from the authenticated Spotify account, never a local profile.
        """
        value = self.username or self.display_name
        if not value:
            return "spotapi@spotify ~ $"
        allowed = "".join(
            (
                character
                if character.isascii() and (character.isalnum() or character in "_-")
                else "_"
            )
            for character in value.strip()
        ).strip("_")
        return f"spotapi@{allowed[:20]} ~ $" if allowed else "spotapi@spotify ~ $"


def _short(value: str, width: int) -> str:
    """Keep interactive rows scannable even in an IDE terminal."""
    value = value.replace("\r", " ").replace("\n", " ").strip()
    return value if cell_len(value) <= width else set_cell_size(value, width - 1).rstrip() + "…"


def search_row(index: int, hit: Track) -> str:
    """A compact numbered track row, with real (optional) Spotify metadata."""
    title = _short(hit.name, 34)
    artist_names = (
        ", ".join(
            artist.profile.name for artist in hit.artists.items if artist.profile is not None
        )
        if hit.artists is not None
        else ""
    )
    detail = _short(artist_names, 24)
    duration = clock(hit.duration.total_milliseconds) if hit.duration else ""
    tail = "  ·  ".join(part for part in (detail, duration) if part)
    return f"{index:02}  {title}" + (f"   ·   {tail}" if tail else "")


def device_row(index: int, device: Device, *, active: str | None, target: str | None) -> str:
    """Distinguish Spotify's actual playback device from a selected target."""
    status = (
        "● playing" if device.id == active else "◎ target" if device.id == target else "○ ready"
    )
    name = _short(device.name, 32)
    return f"{index:02}  {status}   {name}   ·   {_short(device.type, 14)}"
