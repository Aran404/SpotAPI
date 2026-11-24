"""Match local music against LRCLIB and save lyrics without silent overwrites."""

from __future__ import annotations

import importlib
import importlib.util
import json
import math
import os
import re
import shutil
import sys
import tempfile
import unicodedata
from collections import Counter
from dataclasses import dataclass
from difflib import unified_diff
from importlib.metadata import version
from pathlib import Path
from time import sleep
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

_SUFFIXES = {".flac", ".mp3"}
_TIMESTAMP = re.compile(r"(?m)^\[\d+:[0-5]\d(?:\.\d+)?\]")


@dataclass(frozen=True, slots=True)
class Track:
    path: Path
    title: str
    artist: str
    album: str
    duration: float
    embedded: tuple[str, ...] = ()
    timed: bool = False
    signature: tuple[int, int, int] | None = None


@dataclass(frozen=True, slots=True)
class Lyrics:
    text: str
    synced: bool

    @property
    def suffix(self) -> str:
        return ".lrc" if self.synced else ".txt"


def _signature(path: Path) -> tuple[int, int, int]:
    stat = path.stat()
    return stat.st_ino, stat.st_size, stat.st_mtime_ns


def _read_track(path: Path) -> Track:
    signature = _signature(path)
    mutagen: Any = importlib.import_module("mutagen")
    try:
        audio: Any = mutagen.File(path, easy=True)
        raw: Any = mutagen.File(path)
        if audio is None or raw is None:
            raise ValueError("unsupported audio file")
        title = str((audio.get("title") or [""])[0]).strip()
        artist = str((audio.get("artist") or [""])[0]).strip()
        album = str((audio.get("album") or [""])[0]).strip()
        duration = float(audio.info.length)
        if not title or not artist or not math.isfinite(duration) or duration <= 0:
            raise ValueError("missing title, artist or duration")
        if duration > 3600:
            raise ValueError("duration exceeds LRCLIB's one-hour limit")

        if path.suffix.lower() == ".flac":
            embedded = tuple(str(value) for value in raw.get("lyrics", []))
            timed = any(_TIMESTAMP.search(value) for value in embedded)
        elif raw.tags is not None:
            embedded = tuple(str(frame.text) for frame in raw.tags.getall("USLT"))
            timed = bool(raw.tags.getall("SYLT"))
        else:
            embedded, timed = (), False

        return Track(path, title, artist, album, duration, embedded, timed, signature)
    except mutagen.MutagenError as error:
        raise ValueError(f"cannot read audio metadata: {error}") from error


def _normalized(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _match(record: dict[str, object], track: Track) -> Lyrics | None:
    if record.get("instrumental") is True:
        return None
    duration = record.get("duration")
    if isinstance(duration, bool) or not isinstance(duration, (int, float)):
        return None
    if not math.isfinite(duration):
        return None
    if abs(duration - track.duration) > 2:
        return None
    for key, expected in (
        ("trackName", track.title),
        ("artistName", track.artist),
        ("albumName", track.album),
    ):
        actual = record.get(key)
        if expected and (
            not isinstance(actual, str) or _normalized(actual) != _normalized(expected)
        ):
            return None

    synced = record.get("syncedLyrics")
    if isinstance(synced, str) and _TIMESTAMP.search(synced):
        return Lyrics(synced.strip() + "\n", True)
    plain = record.get("plainLyrics")
    if isinstance(plain, str) and plain.strip():
        return Lyrics(plain.strip() + "\n", False)
    return None


def _lookup(track: Track) -> Lyrics | None:
    params: dict[str, str | int] = {
        "track_name": track.title,
        "artist_name": track.artist,
        "duration": max(1, round(track.duration)),
    }
    if track.album:
        params["album_name"] = track.album
    query = urlencode(params)
    agent = f"SpotAPI/{version('spotapi')} (https://github.com/Aran404/SpotAPI)"
    request = Request(f"https://lrclib.net/api/get?{query}", headers={"User-Agent": agent})
    try:
        with urlopen(request, timeout=20) as response:
            if response.headers.get_content_type() != "application/json":
                raise ValueError("LRCLIB returned a non-JSON response")
            body = response.read(1_000_001)
    except HTTPError as error:
        if error.code == 404:
            return None
        if error.code in {429, 503}:
            retry = error.headers.get("Retry-After")
            reason = "rate limit reached" if error.code == 429 else "temporarily unavailable"
            delay = f" (Retry-After: {_visible(retry)})" if retry else ""
            raise RuntimeError(f"LRCLIB {reason}; try again later{delay}") from error
        raise RuntimeError(f"LRCLIB returned HTTP {error.code}") from error
    except URLError as error:
        raise RuntimeError(f"LRCLIB is unavailable: {error.reason}") from error

    if len(body) > 1_000_000:
        raise ValueError("LRCLIB response exceeds 1 MB")
    record: object = json.loads(body)
    if not isinstance(record, dict):
        raise ValueError("LRCLIB returned an invalid record")
    return _match(cast("dict[str, object]", record), track)


def _read_text(path: Path) -> str | None:
    if path.is_symlink():
        raise ValueError(f"refusing symbolic link: {path}")
    return path.read_text(encoding="utf-8-sig") if path.exists() else None


def _write_text(path: Path, text: str, previous: str | None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".spotapi-", dir=path.parent) as directory:
        staged = Path(directory) / "lyrics"
        staged.write_text(text, encoding="utf-8", newline="\n")
        if _read_text(path) != previous:
            raise ValueError("lyrics changed since review")
        if previous is None:
            if os.name == "nt":
                staged.rename(path)
            else:
                os.link(staged, path)
        else:
            shutil.copymode(path, staged)
            staged.replace(path)


def _embed(track: Track, lyrics: Lyrics) -> None:
    path = track.path
    original = _signature(path)
    if path.is_symlink() or original != track.signature:
        raise ValueError("audio changed since review")
    mutagen: Any = importlib.import_module("mutagen")
    with tempfile.TemporaryDirectory(prefix=".spotapi-", dir=path.parent) as directory:
        staged = Path(directory) / path.name
        shutil.copy2(path, staged)
        try:
            audio: Any = mutagen.File(staged)
            if audio is None:
                raise ValueError("unsupported audio file")
            if path.suffix.lower() == ".flac":
                audio["lyrics"] = [lyrics.text.rstrip("\n")]
            else:
                id3: Any = importlib.import_module("mutagen.id3")
                tags: Any = audio.tags
                if tags is None:
                    raise ValueError("audio tags disappeared since review")
                tags.delall("USLT")
                tags.add(id3.USLT(encoding=3, lang="und", desc="", text=lyrics.text))
            audio.save()
        except mutagen.MutagenError as error:
            raise ValueError(f"cannot embed lyrics: {error}") from error
        if path.is_symlink() or _signature(path) != original:
            raise ValueError("audio changed since review")
        staged.replace(path)


def _visible(text: str) -> str:
    return "".join(
        char if char.isprintable() or char == "\n" else repr(char)[1:-1] for char in text
    )


def _review(previous: str, lyrics: Lyrics, *, dry_run: bool) -> bool:
    print(
        _visible(
            "\n".join(
                unified_diff(
                    previous.splitlines(),
                    lyrics.text.splitlines(),
                    fromfile="existing",
                    tofile="LRCLIB",
                    lineterm="",
                )
            )
        )
    )
    if dry_run:
        return True
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False
    try:
        return input("  Apply this change? [y/N] ").strip().lower() in {"y", "yes"}
    except EOFError:
        return False


def _save(track: Track, lyrics: Lyrics, destination: Path, *, embed: bool, dry_run: bool) -> str:
    # MP3 synchronized lyrics remain LRC sidecars; USLT is not a timed tag.
    embed = embed and (track.path.suffix.lower() == ".flac" or not lyrics.synced)
    lrc = _read_text(destination.with_suffix(".lrc"))
    plain = _read_text(destination.with_suffix(".txt"))
    if not lyrics.synced and (lrc is not None or track.timed):
        return "Kept synced"
    if embed and len(track.embedded) > 1:
        return "Kept embedded"
    if track.timed and not track.embedded and lrc is None:
        return "Kept embedded"

    target = destination.with_suffix(lyrics.suffix)
    existing = lrc if lyrics.synced else plain
    if embed and track.embedded:
        previous = track.embedded[0]
    else:
        previous = existing
        if previous is None:
            previous = plain if lyrics.synced else None
        if previous is None and track.embedded:
            previous = "\n".join(track.embedded)

    if previous is not None:
        if previous.strip() == lyrics.text.strip():
            if not embed or track.embedded:
                return "Unchanged"
        else:
            print(f"  Review: {_visible(str(track.path))}")
            if not _review(previous, lyrics, dry_run=dry_run):
                return "Kept existing"
    if dry_run:
        return "Would embed" if embed else f"Would save {lyrics.suffix}"
    if embed:
        _embed(track, lyrics)
        return "Embedded"
    _write_text(target, lyrics.text, existing)
    return f"Saved {lyrics.suffix}"


def run(path: Path, *, output: Path | None, embed: bool, dry_run: bool) -> int:
    """Process a file or directory, preserving existing lyrics by default."""
    if importlib.util.find_spec("mutagen") is None:
        raise RuntimeError('Install lyrics sync with: pip install "spotapi[media]"')
    if not path.exists() or path.is_symlink():
        raise ValueError(f"not a local audio file or directory: {path}")
    root = path if path.is_dir() else path.parent
    files = sorted(
        file
        for file in (path.rglob("*") if path.is_dir() else (path,))
        if file.is_file() and not file.is_symlink() and file.suffix.lower() in _SUFFIXES
    )
    if not files:
        raise ValueError("no MP3 or FLAC files found")

    destinations = [output / file.relative_to(root) if output else file for file in files]
    stems = Counter(str(file.with_suffix("")).casefold() for file in destinations)
    counts: Counter[str] = Counter()
    requested = False
    print(f"LRCLIB | {len(files)} track{'s' if len(files) != 1 else ''}")
    if dry_run:
        print("Dry run: no files will be changed.")
    print()

    for file, destination in zip(files, destinations, strict=True):
        label = _visible(str(file.relative_to(root)))
        try:
            if stems[str(destination.with_suffix("")).casefold()] > 1:
                raise ValueError("multiple audio files share this lyrics filename")
            if not destination.parent.resolve().is_relative_to((output or root).resolve()):
                raise ValueError("output path escapes the destination directory")
            track = _read_track(file)
            # LRCLIB asks batch clients to space requests and avoid concurrency.
            if requested:
                sleep(0.75)
            requested = True
            lyrics = _lookup(track)
            status = (
                "Not found"
                if lyrics is None
                else _save(track, lyrics, destination, embed=embed, dry_run=dry_run)
            )
        except (OSError, ValueError) as error:
            status = "Skipped"
            label += f" ({_visible(str(error))})"
        counts[status] += 1
        print(f"  {status:<16} {label}")

    print("\n" + " | ".join(f"{count} {status.lower()}" for status, count in counts.items()))
    return int(counts["Skipped"] > 0)
