"""Thin, typed orchestration around the existing Spotify Connect player."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, cast

from .commands import Command, duration_ms

if TYPE_CHECKING:
    from spotapi.catalogue import Catalogue
    from spotapi.models.catalogue.track import Track
    from spotapi.models.playback import Device
    from spotapi.player import Player


@dataclass(frozen=True, slots=True)
class Result:
    """User-facing outcome of one explicit command."""

    message: str
    search_hits: tuple[Track, ...] | None = None


def _device_at(devices: tuple[Device, ...], value: str) -> Device:
    number = int(value)
    if not 1 <= number <= len(devices):
        raise ValueError("That device is not listed. Run /devices first")
    return devices[number - 1]


def _resource(value: str, hits: tuple[Track, ...]) -> str:
    """Resolve an explicit Spotify URL or the index of a displayed search hit."""
    if value.isascii() and value.isdecimal():
        number = int(value)
        if not 1 <= number <= len(hits):
            raise ValueError("Result number not found. Run /search first")
        return hits[number - 1].uri
    return value


async def execute(
    command: Command,
    *,
    player: Player,
    catalogue: Catalogue,
    hits: tuple[Track, ...] = (),
) -> Result:
    """Execute one action without retries or implicit Spotify state mutations."""
    action, argument = command.action, command.argument

    match action:
        case "help":
            return Result(
                "COMMANDS\n"
                "  /devices    list players       /use 1      target only\n"
                "  /transfer 1 move playback      next / previous\n"
                "  pause / resume / toggle        seek 1:30\n"
                "  volume 60   shuffle on|off     repeat off|context|track\n"
                "  search Daft Punk               play 1 / queue 1\n"
                "  play spotify:track:...        /refresh /clear /exit\n"
                "  Ctrl+K suggest; ←→ switch views; Ctrl+J browse; Esc prompt; F2 logs.\n"
                "  ↑↓ select; Enter plays a track/targets device; Q queues; T transfers."
            )
        case "quit":
            return Result("Session closing")
        case "clear":
            # The UI owns the log buffers; also safe for headless execute callers.
            return Result("Activity and diagnostics cleared")
        case "devices":
            if not player.devices:
                return Result("No players found. Open Spotify on a device and try /refresh")
            lines = ["AVAILABLE SPOTIFY DEVICES"]
            for index, device in enumerate(player.devices, 1):
                labels: list[str] = []
                if device.id == player.target_device_id:
                    labels.append("TARGET")
                if player.state and device.id == player.state.active_device_id:
                    labels.append("PLAYING")
                lines.append(f"  {index}. {device.name}  {device.type}  {' · '.join(labels)}")
            lines.append("Use /use N to target a device; /transfer N to move playback.")
            return Result("\n".join(lines))
        case "search":
            result = await catalogue.search(argument, types="track", limit=20)
            found = result.tracks
            if not found:
                return Result(f"No tracks found for {argument!r}", ())
            lines = [f"TRACKS · {argument}"]
            for index, hit in enumerate(found, 1):
                lines.append(f"  {index}. {hit.name}")
            lines.append("/play 1 or /queue 1 · or use a Spotify URI")
            return Result("\n".join(lines), found)
        case _:
            pass  # Mutations are validated below, after checking readiness.

    if not player.is_ready:
        raise RuntimeError("Connecting to Spotify. Commands are available when ready")

    match action:
        case "use":
            device = _device_at(player.devices, argument)
            player.select(device)
            return Result(f"Target set: {device.name}. Playback was not transferred")
        case "transfer":
            device = _device_at(player.devices, argument)
            await player.transfer(device)
            return Result(f"Transfer requested: {device.name}. Waiting for Spotify state")
        case "pause":
            await player.pause()
        case "resume":
            await player.resume()
        case "toggle":
            state = player.state
            if state is None or player.target_device_id not in (None, state.active_device_id):
                raise ValueError("Select the active device before toggling playback")
            if state.is_paused:
                await player.resume()
            else:
                await player.pause()
        case "next":
            await player.next()
        case "previous":
            await player.previous()
        case "seek":
            await player.seek(duration_ms(argument))
        case "volume":
            await player.volume(int(argument))
        case "shuffle":
            await player.shuffle(argument == "on")
        case "repeat":
            await player.repeat(cast(Literal["off", "context", "track"], argument))
        case "play":
            await player.play(_resource(argument, hits))
        case "queue":
            await player.add_to_queue(_resource(argument, hits))
        case "refresh":
            await player.refresh()
            return Result("Fresh Spotify state requested")
        case _:
            raise ValueError(f"Unsupported command: {action}")

    # The Connect backend awaits a dealer ACK or matching state where supported.
    # Do not imply the audio already changed, or retry after an ambiguous timeout.
    return Result(f"{action.capitalize()} accepted · observing Spotify for state changes")
