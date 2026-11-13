"""Read public lyrics from LRCLIB without sharing a Spotify session."""

from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import timedelta
from typing import cast

import wreq

from spotapi.models import LyricLine, Lyrics, TrackDetails

_STAMP = re.compile(r"\[(\d{1,3}):([0-5]\d)(?:\.(\d{1,3}))?\]")


def parse_lyrics(record: Mapping[str, object]) -> Lyrics | None:
    """Read LRC timings or display plain text without inventing timings."""
    if record.get("instrumental") is True:
        return None

    synced = record.get("syncedLyrics")
    lines: list[LyricLine] = []
    if isinstance(synced, str):
        for row in synced.splitlines():
            stamps: list[int] = []
            while stamp := _STAMP.match(row):
                minutes, seconds, fraction = stamp.groups()
                stamps.append(
                    60_000 * int(minutes)
                    + 1000 * int(seconds)
                    + int((fraction or "").ljust(3, "0"))
                )
                row = row[stamp.end() :]
            if words := row.strip():
                lines.extend(LyricLine(time, words) for time in stamps)

    if lines:
        return Lyrics(
            "LINE_SYNCED", tuple(sorted(lines, key=lambda line: line.start_time_ms)), "LRCLIB"
        )

    plain = record.get("plainLyrics")
    if isinstance(plain, str) and plain.strip():
        return Lyrics("UNSYNCED", tuple(LyricLine(0, row) for row in plain.splitlines()), "LRCLIB")

    return None


async def get_public_lyrics(track: TrackDetails) -> Lyrics | None:
    """Match the recording by title, artist, album and duration."""
    artists = track.first_artist.items if track.first_artist else []
    profile = artists[0].profile if artists else None
    duration = track.duration.total_milliseconds / 1000
    if not profile or not profile.name or not 1 <= duration <= 3600:
        return None

    client = wreq.Client(
        timeout=timedelta(seconds=5),
        redirect=wreq.redirect.Policy.none(),
        user_agent="SpotAPI Studio v2.0.0 (https://github.com/Aran404/SpotAPI)",
    )
    query = {
        "track_name": track.name,
        "artist_name": profile.name,
        "duration": str(duration),
    }
    if track.album_of_track is not None:
        query["album_name"] = track.album_of_track.name

    try:
        response = await client.get("https://lrclib.net/api/get", query=query)
        status = response.status.as_int()
        if status == 404:
            return None
        if status != 200:
            raise ValueError(f"LRCLIB is unavailable (HTTP {status}).")
        record: object = await response.json()
        return (
            parse_lyrics(cast(Mapping[str, object], record))
            if isinstance(record, Mapping)
            else None
        )
    except (
        wreq.exceptions.ConnectionError,
        wreq.exceptions.TimeoutError,
        wreq.exceptions.TlsError,
    ) as error:
        raise ValueError("Could not connect to LRCLIB.") from error
    finally:
        client.close()
