"""Typed snapshots of Connect devices and playback, without media manifests."""

from __future__ import annotations

import math
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from spotapi._parsing import integer, mapping, records


@dataclass(frozen=True, slots=True)
class PlaybackTrack:
    """A playback or queue occurrence with optional display metadata.

    ``uid`` distinguishes repeated occurrences of the same URI. ``provider``
    identifies their source when supplied. ``duration_ms`` uses milliseconds;
    empty display fields can occur before metadata is loaded.
    """

    uri: str
    name: str = ""
    artist: str = ""
    album: str = ""
    image_url: str | None = None
    duration_ms: int = 0
    uid: str | None = None
    provider: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PlaybackTrack:
        """Parse a Spotify playback snapshot without exposing media manifests."""
        metadata = mapping(value.get("metadata")) or value
        authors = records(metadata.get("authors"))
        images = records(metadata.get("images"))

        return cls(
            uri=str(value.get("uri") or metadata.get("uri") or ""),
            name=str(metadata.get("title") or metadata.get("name") or ""),
            artist=str(
                metadata.get("artist_name") or ", ".join(str(a.get("name", "")) for a in authors)
            ),
            album=str(metadata.get("album_title") or metadata.get("group_name") or ""),
            image_url=metadata.get("image_url") or (images[0].get("url") if images else None),
            duration_ms=integer(metadata.get("duration")),
            uid=value.get("uid"),
            provider=value.get("provider"),
        )


@dataclass(frozen=True, slots=True)
class Device:
    """A playback device from the latest Connect snapshot.

    ``volume`` uses Spotify's native 0-65535 scale; ``volume_percent`` converts
    it to 0-100. Capabilities are observations from the snapshot, not a promise
    that every command is available for the current content.
    """

    id: str
    name: str
    type: str = ""
    volume: int | None = None
    can_play: bool = False
    is_active: bool = False
    is_controllable: bool | None = None
    volume_steps: int | None = None

    @property
    def volume_percent(self) -> int | None:
        """Convert the native Connect volume to a percentage when supplied."""
        if self.volume is None:
            return None

        return round(self.volume * 100 / 65535)


@dataclass(frozen=True, slots=True)
class PlaybackQuality:
    """Observed playback quality metadata from Connect.

    These fields describe the snapshot and do not remotely configure bitrate
    or authorize access to media.
    """

    bitrate: str | None = None
    target_bitrate: str | None = None
    target_available: bool | None = None
    strategy: str | None = None
    file_origin: str | None = None

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> PlaybackQuality:
        """Parse a Spotify playback snapshot without exposing media manifests."""
        return cls(
            bitrate=value.get("bitrate_level"),
            target_bitrate=value.get("target_bitrate_level"),
            target_available=value.get("target_bitrate_available"),
            strategy=value.get("strategy"),
            file_origin=value.get("file_origin"),
        )


@dataclass(frozen=True, slots=True)
class PlayerState:
    """A timestamped Connect snapshot with queue, options and restrictions.

    ``position`` is the reported millisecond anchor; ``position_ms`` projects
    current position using the local monotonic clock and playback speed. Queue
    entries preserve occurrence UIDs. Inspecting properties never sends a request.
    """

    timestamp: int
    active_device_id: str | None
    track: PlaybackTrack | None
    position: int
    duration_ms: int
    is_playing: bool
    is_paused: bool
    playback_speed: float
    context_uri: str | None
    next_tracks: tuple[PlaybackTrack, ...] = ()
    prev_tracks: tuple[PlaybackTrack, ...] = ()
    shuffle: bool = False
    repeat_context: bool = False
    repeat_track: bool = False
    queue_revision: str | None = None
    track_index: int | None = None
    quality: PlaybackQuality = field(default_factory=PlaybackQuality)
    modes: dict[str, str] = field(default_factory=dict[str, str])
    restrictions: dict[str, tuple[str, ...]] = field(default_factory=dict[str, tuple[str, ...]])
    position_timestamp: int | None = None
    signals: tuple[str, ...] = ()
    server_timestamp: int | None = field(default=None, compare=False)
    received_at: float = field(default_factory=time.monotonic, compare=False, repr=False)

    @property
    def position_ms(self) -> int:
        """Estimate current playback position from the timestamped snapshot."""
        elapsed = (
            0.0 if self.is_paused or not self.is_playing else time.monotonic() - self.received_at
        )
        snapshot_age = (
            max(0, (self.server_timestamp or self.timestamp) - self.position_timestamp)
            if self.is_playing and self.position_timestamp is not None
            else 0
        )

        return min(
            self.duration_ms,
            max(0, self.position + int((elapsed * 1000 + snapshot_age) * self.playback_speed)),
        )

    @property
    def remaining_ms(self) -> int:
        """Return estimated remaining playback time, clamped at zero."""
        return max(0, self.duration_ms - self.position_ms)

    @property
    def progress(self) -> float:
        """Return estimated track progress between zero and one."""
        return self.position_ms / self.duration_ms if self.duration_ms > 0 else 0.0

    @property
    def repeat_mode(self) -> Literal["off", "context", "track"]:
        """Return the effective off, context or track repeat setting."""
        if self.repeat_track:
            return "track"

        return "context" if self.repeat_context else "off"

    def allows(
        self, action: Literal["pause", "resume", "seek", "next", "previous", "shuffle", "repeat"]
    ) -> bool:
        """Check Spotify's current restrictions for a supported player action."""
        names = {
            "pause": "pausing",
            "resume": "resuming",
            "seek": "seeking",
            "next": "skipping_next",
            "previous": "skipping_prev",
            "shuffle": "toggling_shuffle",
            "repeat": "toggling_repeat_context",
        }

        if action not in names:
            raise ValueError("Unknown player action")

        return not self.restrictions.get("disallow_" + names[action] + "_reasons")

    @classmethod
    def from_cluster(cls, cluster: Mapping[str, Any]) -> PlayerState:
        """Parse the account-wide Connect cluster into a timestamped player snapshot."""
        value = mapping(cluster.get("player_state"))
        options = mapping(value.get("options"))
        track = mapping(value.get("track"))
        speed = value.get("playback_speed", 1.0)
        restrictions: dict[str, tuple[str, ...]] = {}

        for key, reasons in mapping(value.get("restrictions")).items():
            if isinstance(reasons, list):
                restrictions[key] = tuple(
                    reason for reason in cast(list[object], reasons) if isinstance(reason, str)
                )

        modes: dict[str, str] = {}

        for key, mode in mapping(options.get("modes")).items():
            if isinstance(mode, str):
                modes[key] = mode

        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or speed < 0
        ):
            speed = 1.0

        signals = value.get("signals")
        if not isinstance(signals, list):
            signals = []

        return cls(
            timestamp=integer(cluster.get("timestamp")),
            active_device_id=cluster.get("active_device_id") or None,
            track=PlaybackTrack.from_dict(track) if track else None,
            position=integer(value.get("position_as_of_timestamp")),
            duration_ms=integer(value.get("duration")),
            is_playing=value.get("is_playing") is True and value.get("is_paused") is False,
            is_paused=value.get("is_paused", True) is True,
            playback_speed=float(speed),
            context_uri=value.get("context_uri") or None,
            next_tracks=tuple(
                PlaybackTrack.from_dict(t) for t in records(value.get("next_tracks"))
            ),
            prev_tracks=tuple(
                PlaybackTrack.from_dict(t) for t in records(value.get("prev_tracks"))
            ),
            shuffle=options.get("shuffling_context") is True,
            repeat_context=options.get("repeating_context") is True,
            repeat_track=options.get("repeating_track") is True,
            queue_revision=value.get("queue_revision"),
            track_index=mapping(value.get("index")).get("track"),
            quality=PlaybackQuality.from_dict(mapping(value.get("playback_quality"))),
            modes=modes,
            restrictions=restrictions,
            signals=tuple(
                signal for signal in cast(list[object], signals) if isinstance(signal, str)
            ),
            position_timestamp=integer(value["timestamp"]) if "timestamp" in value else None,
            server_timestamp=integer(cluster.get("server_timestamp_ms")) or None,
        )


@dataclass(frozen=True, slots=True)
class PlaybackUpdate:
    """A renderer state-machine update, separate from account-wide Connect state.

    ``state_index`` selects a state within the returned machine. ``position_ms``
    reflects a supplied seek target when present, not a continuously updated clock.
    """

    state_machine_id: str
    state_id: str | None
    state_index: int
    paused: bool
    position_ms: int | None
    track: PlaybackTrack | None

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> PlaybackUpdate:
        """Parse a Spotify playback snapshot without exposing media manifests."""
        machine = mapping(payload.get("state_machine"))
        ref = mapping(payload.get("state_ref"))
        states = records(machine.get("states"))
        tracks = records(machine.get("tracks"))
        index = integer(ref.get("state_index"), -1)
        state: Mapping[str, Any] = states[index] if 0 <= index < len(states) else {}
        track_index = integer(state.get("track"), -1)
        track: Mapping[str, Any] = tracks[track_index] if 0 <= track_index < len(tracks) else {}

        return cls(
            str(machine.get("state_machine_id", "")),
            state.get("state_id"),
            index,
            ref.get("paused") is True,
            integer(payload["seek_to"]) if payload.get("seek_to") is not None else None,
            PlaybackTrack.from_dict(track) if track else None,
        )
