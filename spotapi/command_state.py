"""Confirm Connect commands from dealer state when a device omits its ACK."""

from collections.abc import Mapping
from typing import Any

from spotapi.models.playback import PlayerState

from ._parsing import mapping, records


def command_applied(
    endpoint: str,
    arguments: Mapping[str, Any],
    before: PlayerState | None,
    current: PlayerState | None,
) -> bool:
    """Require a fresh snapshot proving a known command's requested result; never resend it."""
    if current is None or current is before:
        return False
    if before is not None and current.active_device_id != before.active_device_id:
        return False
    if before is not None and current.timestamp <= before.timestamp:
        return False
    if endpoint == "pause":
        return current.is_paused
    if endpoint == "resume":
        return current.is_playing and not current.is_paused
    if endpoint in {"skip_next", "skip_prev"}:
        return (
            before is not None
            and current.track is not None
            and (
                before.track is None
                or (current.track.uri, current.track.uid) != (before.track.uri, before.track.uid)
            )
        )
    if endpoint == "seek_to":
        position = arguments.get("position")
        return type(position) is int and abs(current.position_ms - position) < 1500
    if endpoint == "set_shuffling_context":
        return current.shuffle is arguments.get("value")
    if endpoint == "set_options":
        options = {
            "repeating_context": current.repeat_context,
            "repeating_track": current.repeat_track,
        }
        supplied = {key: value for key, value in arguments.items() if key in options}
        return bool(supplied) and all(options[key] is value for key, value in supplied.items())
    if endpoint == "add_to_queue" and before is not None:
        uri = mapping(arguments.get("track")).get("uri")
        previous_count = sum(
            track.uri == uri and track.provider == "queue" for track in before.next_tracks
        )
        current_count = sum(
            track.uri == uri and track.provider == "queue" for track in current.next_tracks
        )
        return current_count > previous_count
    if endpoint == "set_queue":
        requested = records(arguments.get("next_tracks"))
        if len(requested) != len(current.next_tracks):
            return False
        return all(
            expected.get("uri") == actual.uri
            and (not expected.get("uid") or expected["uid"] == actual.uid)
            for expected, actual in zip(requested, current.next_tracks, strict=True)
        )
    if endpoint == "play" and current.is_playing and current.track is not None:
        uri = mapping(arguments.get("context")).get("uri")
        return current.track.uri == uri or current.context_uri == uri
    return False
