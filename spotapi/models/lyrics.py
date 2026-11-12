"""Lyrics text, syllable timings and local position lookup."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from spotapi._parsing import integer, mapping, records
from spotapi.types import BaseClientError


@dataclass(frozen=True, slots=True)
class LyricSyllable:
    """A syllable timing in milliseconds and its reported character count."""

    start_time_ms: int
    num_chars: int

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> LyricSyllable:
        """Parse lyrics metadata and reject malformed timing or text fields."""
        start = integer(value.get("startTimeMs"), -1)
        length = integer(value.get("numChars"), -1)

        if start < 0 or length < 0:
            raise BaseClientError("Spotify returned an invalid lyric syllable")

        return cls(start, length)


@dataclass(frozen=True, slots=True)
class LyricLine:
    """One lyric line with millisecond timings and optional syllable metadata.

    An unknown or zero end time is represented by None. Several lines may share
    the same start time; consumers should preserve those duplicate timestamps.
    """

    start_time_ms: int
    words: str
    end_time_ms: int | None = None
    syllables: tuple[LyricSyllable, ...] = ()
    transliterated_words: str = ""

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> LyricLine:
        """Parse lyrics metadata and reject malformed timing or text fields."""
        start = integer(value.get("startTimeMs"), -1)
        end = integer(value.get("endTimeMs"), 0)
        words = value.get("words")

        if start < 0 or end < 0 or not isinstance(words, str):
            raise BaseClientError("Spotify returned an invalid lyric line")

        syllables = tuple(
            LyricSyllable.from_dict(item) for item in records(value.get("syllables"))
        )

        return cls(
            start_time_ms=start,
            words=words,
            end_time_ms=end or None,
            syllables=syllables,
            transliterated_words=str(value.get("transliteratedWords") or ""),
        )


@dataclass(frozen=True, slots=True)
class Lyrics:
    """Lyrics text, timing mode and provider metadata.

    ``at(position_ms)`` returns all active lines for LINE_SYNCED lyrics. It
    returns an empty tuple for unsynchronized text. The model does not poll
    a player or advance a clock by itself.
    """

    sync_type: str
    lines: tuple[LyricLine, ...]
    provider: str = ""
    language: str = ""
    is_rtl: bool = False

    @classmethod
    def from_dict(cls, body: Mapping[str, Any]) -> Lyrics:
        """Parse lyrics metadata and reject malformed timing or text fields."""
        value = mapping(body.get("lyrics", body))

        if not value or not isinstance(value.get("lines"), list):
            raise BaseClientError("Spotify returned no lyrics")

        lines = tuple(LyricLine.from_dict(line) for line in records(value["lines"]))

        if any(before.start_time_ms > after.start_time_ms for before, after in pairwise(lines)):
            raise BaseClientError("Spotify returned lyrics out of timestamp order")

        return cls(
            sync_type=str(value.get("syncType", "UNSYNCED")),
            lines=lines,
            provider=str(value.get("provider") or ""),
            language=str(value.get("language") or ""),
            is_rtl=value.get("isRtlLanguage") is True,
        )

    def at(self, position_ms: int) -> tuple[LyricLine, ...]:
        """Return all lines sharing the current timestamp, or an empty tuple."""
        if self.sync_type != "LINE_SYNCED":
            return ()

        end = bisect_right(self.lines, position_ms, key=lambda line: line.start_time_ms)

        if not end:
            return ()

        start = end - 1

        while start and self.lines[start - 1].start_time_ms == self.lines[end - 1].start_time_ms:
            start -= 1

        return tuple(
            line
            for line in self.lines[start:end]
            if line.end_time_ms is None or position_ms < line.end_time_ms
        )
