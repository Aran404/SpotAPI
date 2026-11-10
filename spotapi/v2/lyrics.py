"""Premium lyrics obtained with the caller's authorized Spotify session."""

from __future__ import annotations

from bisect import bisect_right
from collections.abc import Mapping
from dataclasses import dataclass
from itertools import pairwise
from typing import Any
from urllib.parse import quote, urlsplit

from .catalogue import parse_spotify_resource
from .client import AsyncClient
from .connect import ConnectEndpoints
from .playback import integer, mapping, records
from .session import AuthSession
from .types import BaseClientError


@dataclass(frozen=True, slots=True)
class LyricSyllable:
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


class LyricsClient:
    """Use ``await LyricsClient(client).get(track, image_url=cover)``."""

    def __init__(self, session: AuthSession | AsyncClient) -> None:
        """Borrow an authenticated client; resolve lyrics hosts lazily."""
        self.session = session.session if isinstance(session, AsyncClient) else session
        self._endpoints: ConnectEndpoints | None = None

    async def get(self, track: str, *, image_url: str | None = None) -> Lyrics:
        """Fetch available lyrics for a track; requires Spotify's Premium entitlement."""
        resource = parse_spotify_resource(track, "track")
        path = "/color-lyrics/v2/track/" + quote(resource.id, safe="")

        if image_url is not None:
            if urlsplit(image_url).scheme != "https":
                raise ValueError("image_url must be an HTTPS image URL")

            path += "/image/" + quote(image_url, safe="")

        if self._endpoints is None:
            self._endpoints = await ConnectEndpoints.resolve(self.session)

        response = await self.session.client.get(
            self._endpoints.spclient + path,
            headers={**self.session.authorized_headers, "accept": "application/json"},
            query={"format": "json", "vocalRemoval": "false", "market": "from_token"},
        )

        return Lyrics.from_dict(mapping(response.json))
