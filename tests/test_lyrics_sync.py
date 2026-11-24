"""Local lyrics matching, review and file safety."""

from __future__ import annotations

import base64
import importlib
import io
import json
from dataclasses import replace
from email.message import Message
from pathlib import Path
from typing import Any
from unittest.mock import Mock
from urllib.error import HTTPError, URLError

import pytest

from spotapi import _lyrics_sync as sync
from spotapi.cli import _parser, main

# A short, silent FLAC recording; no copyrighted audio or lyrics are used.
_FLAC = (
    "ZkxhQwAAACICQAJAAAALAAAMAfQA8AAAAyBq0A9H2K1PEgBbIrLKpI94hAAADgYAAABmZm1wZWc"
    "AAAAA//gkCADKAAAAznb/+GQIAd/lAAAAzwo="
)


class _Response(io.BytesIO):
    def __init__(self, body: bytes, content_type: str = "application/json") -> None:
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


@pytest.fixture(autouse=True)
def no_network_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "sleep", Mock())


@pytest.fixture
def track(tmp_path: Path) -> sync.Track:
    path = tmp_path / "été.flac"
    path.write_bytes(base64.b64decode(_FLAC))
    flac: Any = importlib.import_module("mutagen.flac")
    audio: Any = flac.FLAC(path)
    audio["title"] = "Summer"
    audio["artist"] = "Example"
    audio["album"] = "Demo"
    audio.save()
    return sync._read_track(path)


def _record(track: sync.Track, **changes: object) -> dict[str, object]:
    return {
        "trackName": track.title,
        "artistName": track.artist,
        "albumName": track.album,
        "duration": track.duration,
        "plainLyrics": "hello",
        "syncedLyrics": "[00:00.00] hello",
        **changes,
    }


def test_read_and_match(track: sync.Track) -> None:
    assert (track.title, track.artist, track.album) == ("Summer", "Example", "Demo")
    assert not track.embedded
    assert sync._match(_record(track), track) == sync.Lyrics("[00:00.00] hello\n", True)
    assert sync._match(_record(track, syncedLyrics=None), track) == sync.Lyrics("hello\n", False)
    assert sync._match(_record(track, trackName="  SUMMER "), track) is not None


@pytest.mark.parametrize(
    "changes",
    [
        {"instrumental": True},
        {"duration": None},
        {"duration": True},
        {"duration": float("inf")},
        {"duration": 50},
        {"trackName": "Different"},
        {"artistName": "Different"},
        {"albumName": "Different"},
        {"plainLyrics": "", "syncedLyrics": "invalid"},
    ],
)
def test_reject_mismatch(track: sync.Track, changes: dict[str, object]) -> None:
    assert sync._match(_record(track, **changes), track) is None


def test_lookup(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        sync, "urlopen", Mock(return_value=_Response(json.dumps(_record(track)).encode()))
    )
    assert sync._lookup(track) == sync.Lyrics("[00:00.00] hello\n", True)


@pytest.mark.parametrize("code", [404, 429, 503])
def test_http_status(track: sync.Track, monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    def fail(*args: object, **kwargs: object) -> Any:
        headers = Message()
        headers["Retry-After"] = "10"
        raise HTTPError("https://lrclib.net", code, "error", headers, None)

    monkeypatch.setattr(sync, "urlopen", fail)
    if code == 404:
        assert sync._lookup(track) is None
    else:
        with pytest.raises(RuntimeError, match="LRCLIB"):
            sync._lookup(track)


def test_network_failure(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(*args: object, **kwargs: object) -> Any:
        raise URLError("offline")

    monkeypatch.setattr(sync, "urlopen", fail)
    with pytest.raises(RuntimeError, match="unavailable"):
        sync._lookup(track)


@pytest.mark.parametrize("body", [b"[]", b"x" * 1_000_001, b"invalid json"])
def test_invalid_response(track: sync.Track, monkeypatch: pytest.MonkeyPatch, body: bytes) -> None:
    monkeypatch.setattr(sync, "urlopen", Mock(return_value=_Response(body)))
    with pytest.raises(ValueError):
        sync._lookup(track)


def test_sidecar_lifecycle(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    path = track.path
    plain = sync.Lyrics("old\n", False)
    timed = sync.Lyrics("[00:00.00] new\n", True)
    assert sync._save(track, plain, path, embed=False, dry_run=True) == "Would save .txt"
    assert not path.with_suffix(".txt").exists()
    assert sync._save(track, plain, path, embed=False, dry_run=False) == "Saved .txt"
    assert sync._save(track, plain, path, embed=False, dry_run=False) == "Unchanged"
    monkeypatch.setattr(sync, "_review", Mock(return_value=False))
    assert sync._save(track, timed, path, embed=False, dry_run=False) == "Kept existing"
    monkeypatch.setattr(sync, "_review", Mock(return_value=True))
    assert sync._save(track, timed, path, embed=False, dry_run=False) == "Saved .lrc"
    assert path.with_suffix(".txt").read_text() == plain.text
    assert path.with_suffix(".lrc").read_text() == timed.text
    assert sync._save(track, plain, path, embed=False, dry_run=False) == "Kept synced"


def test_atomic_replace(tmp_path: Path) -> None:
    path = tmp_path / "lyrics.txt"
    sync._write_text(path, "old\n", None)
    with pytest.raises(ValueError, match="changed"):
        sync._write_text(path, "new\n", None)
    assert path.read_text() == "old\n"
    sync._write_text(path, "new\n", "old\n")
    assert path.read_text() == "new\n"


def test_embed_flac(track: sync.Track) -> None:
    lyrics = sync.Lyrics("[00:00.00] hello\n", True)
    assert sync._save(track, lyrics, track.path, embed=True, dry_run=True) == "Would embed"
    assert not sync._read_track(track.path).embedded
    assert sync._save(track, lyrics, track.path, embed=True, dry_run=False) == "Embedded"
    loaded = sync._read_track(track.path)
    assert loaded.embedded == (lyrics.text.strip(),)
    assert loaded.timed
    assert loaded.title == track.title
    assert loaded.duration == track.duration
    assert sync._save(loaded, lyrics, track.path, embed=True, dry_run=False) == "Unchanged"


def test_review(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    lyrics = sync.Lyrics("new\n", False)
    assert sync._review("old", lyrics, dry_run=True)
    output = capsys.readouterr().out
    assert "-old" in output and "+new" in output
    monkeypatch.setattr(sync.sys.stdin, "isatty", lambda: False)
    assert not sync._review("old", lyrics, dry_run=False)
    monkeypatch.setattr(sync.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sync.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", Mock(return_value="yes"))
    assert sync._review("old", lyrics, dry_run=False)
    monkeypatch.setattr("builtins.input", Mock(return_value=""))
    assert not sync._review("old", lyrics, dry_run=False)


def test_cli(
    track: sync.Track,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(sync, "_lookup", Mock(return_value=sync.Lyrics("hello\n", False)))
    output = tmp_path / "Lyrics"
    assert main(["lyrics-sync", str(track.path), "--output", str(output), "--dry-run"]) == 0
    assert not output.exists()
    assert main(["lyrics-sync", str(track.path), "--output", str(output)]) == 0
    assert (output / "été.txt").read_text(encoding="utf-8") == "hello\n"
    assert "Saved .txt" in capsys.readouterr().out
    assert _parser().parse_args(["lyrics", "abc"]).resource == "abc"
    with pytest.raises(SystemExit):
        _parser().parse_args(["lyrics-sync", str(track.path), "--output", str(output), "--embed"])


def test_recursive_and_collision(
    track: sync.Track, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sync, "_lookup", Mock(return_value=sync.Lyrics("hello\n", False)))
    album = tmp_path / "album"
    album.mkdir()
    moved = album / track.path.name
    track.path.rename(moved)
    output = tmp_path / "lyrics"
    assert sync.run(tmp_path, output=output, embed=False, dry_run=False) == 0
    assert (output / "album" / "été.txt").exists()
    moved.with_suffix(".mp3").touch()
    assert sync.run(tmp_path, output=output, embed=False, dry_run=False) == 1


def test_missing_tracks(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no MP3"):
        sync.run(tmp_path, output=None, embed=False, dry_run=False)
    with pytest.raises(ValueError, match="not a local"):
        sync.run(tmp_path / "missing", output=None, embed=False, dry_run=False)


def test_mp3(tmp_path: Path) -> None:
    # Five silent MPEG frames, produced from a short generated silence clip.
    data = (
        "//sQxAADwAABpAAAACAAADSAAAAETEFNRTMuMTAwVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/+xLEKYPAAAGk"
        "AAAAIAAANIAAAARVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVX/+xDEU4PAAAGkAAAAIAAANIAA"
        "AARVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/7EsR9A8AAAaQAAAAgAAA0gAAABFVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVf/7EMSnA8AAAaQAAAAgAAA0gAAABFVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV"
        "VVVVVVVVVVVV"
    )
    path = tmp_path / "silence.mp3"
    path.write_bytes(base64.b64decode(data))
    id3: Any = importlib.import_module("mutagen.id3")
    tags: Any = id3.ID3()
    tags.add(id3.TIT2(encoding=3, text=["Silence"]))
    tags.add(id3.TPE1(encoding=3, text=["Example"]))
    tags.save(path)
    track = sync._read_track(path)
    plain = sync.Lyrics("hello\n", False)
    assert sync._save(track, plain, path, embed=True, dry_run=False) == "Embedded"
    loaded = sync._read_track(path)
    assert loaded.embedded == (plain.text,)
    assert loaded.title == track.title
    assert loaded.duration == track.duration
    synced = sync.Lyrics("[00:00.00] hello\n", True)
    assert sync._save(loaded, synced, path, embed=True, dry_run=True) == "Would save .lrc"


def test_existing_embedded(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    lyrics = sync.Lyrics("new\n", False)
    multiple = replace(track, embedded=("one", "two"))
    assert sync._save(multiple, lyrics, track.path, embed=True, dry_run=False) == "Kept embedded"
    timed = replace(track, timed=True)
    assert sync._save(timed, lyrics, track.path, embed=False, dry_run=False) == "Kept synced"
    existing = replace(track, embedded=("old",))
    monkeypatch.setattr(sync, "_review", Mock(return_value=False))
    assert sync._save(existing, lyrics, track.path, embed=False, dry_run=False) == "Kept existing"


def test_not_found(
    track: sync.Track, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sync, "_lookup", Mock(return_value=None))
    assert sync.run(track.path, output=None, embed=False, dry_run=False) == 0
    assert "Not found" in capsys.readouterr().out
    assert not track.path.with_suffix(".txt").exists()


def test_invalid_audio(tmp_path: Path) -> None:
    path = tmp_path / "broken.flac"
    path.write_bytes(b"not audio")
    with pytest.raises(ValueError):
        sync._read_track(path)
    assert sync.run(path, output=None, embed=False, dry_run=False) == 1


def test_missing_dependency(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync.importlib.util, "find_spec", Mock(return_value=None))
    with pytest.raises(RuntimeError, match=r"spotapi\[media\]"):
        sync.run(track.path, output=None, embed=False, dry_run=False)


def test_terminal_controls() -> None:
    assert sync._visible("hello\x1b[2J\nworld") == r"hello\x1b[2J" + "\nworld"


def test_review_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    def eof(_: str) -> str:
        raise EOFError

    monkeypatch.setattr(sync.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sync.sys.stdout, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", eof)
    assert not sync._review("old", sync.Lyrics("new\n", False), dry_run=False)


def test_sidecar_symlink(tmp_path: Path) -> None:
    original = tmp_path / "original.txt"
    original.write_text("old", encoding="utf-8")
    alias = tmp_path / "alias.txt"
    try:
        alias.symlink_to(original)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    with pytest.raises(ValueError, match="symbolic link"):
        sync._write_text(alias, "new", None)
    assert original.read_text(encoding="utf-8") == "old"


def test_changed_audio_is_not_replaced(track: sync.Track) -> None:
    original = track.path.read_bytes()
    changed = original + b"changed"
    track.path.write_bytes(changed)
    with pytest.raises(ValueError, match="audio changed"):
        sync._embed(track, sync.Lyrics("hello\n", False))
    assert track.path.read_bytes() == changed


def test_untagged_audio(tmp_path: Path) -> None:
    path = tmp_path / "untagged.flac"
    path.write_bytes(base64.b64decode(_FLAC))
    with pytest.raises(ValueError, match="missing title"):
        sync._read_track(path)


def test_unsupported_audio(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    mutagen: Any = importlib.import_module("mutagen")
    monkeypatch.setattr(mutagen, "File", Mock(return_value=None))
    with pytest.raises(ValueError, match="unsupported audio"):
        sync._read_track(track.path)
    with pytest.raises(ValueError, match="unsupported audio"):
        sync._embed(track, sync.Lyrics("hello\n", False))


def test_failed_embed_preserves_audio(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    mutagen: Any = importlib.import_module("mutagen")
    original = track.path.read_bytes()
    monkeypatch.setattr(mutagen, "File", Mock(side_effect=mutagen.MutagenError("invalid tags")))
    with pytest.raises(ValueError, match="cannot embed"):
        sync._embed(track, sync.Lyrics("hello\n", False))
    assert track.path.read_bytes() == original
    assert list(track.path.parent.iterdir()) == [track.path]


def test_audio_changes_during_embed(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    mutagen: Any = importlib.import_module("mutagen")
    open_audio: Any = mutagen.File
    changed = track.path.read_bytes() + b"concurrent change"

    def modify(path: Path) -> Any:
        track.path.write_bytes(changed)
        return open_audio(path)

    monkeypatch.setattr(mutagen, "File", modify)
    with pytest.raises(ValueError, match="audio changed"):
        sync._embed(track, sync.Lyrics("hello\n", False))
    assert track.path.read_bytes() == changed


def test_embed_identical_sidecar(track: sync.Track) -> None:
    lyrics = sync.Lyrics("hello\n", False)
    sidecar = track.path.with_suffix(".txt")
    sidecar.write_text(lyrics.text, encoding="utf-8")
    assert sync._save(track, lyrics, track.path, embed=True, dry_run=False) == "Embedded"
    assert sync._read_track(track.path).embedded == ("hello",)
    assert sidecar.read_text(encoding="utf-8") == lyrics.text


def test_preserve_existing_timed_tags(track: sync.Track) -> None:
    timed = replace(track, timed=True)
    lyrics = sync.Lyrics("[00:00.00] hello\n", True)
    assert sync._save(timed, lyrics, track.path, embed=False, dry_run=False) == "Kept embedded"
    assert not track.path.with_suffix(".lrc").exists()


def test_output_symlink_escape(
    track: sync.Track, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    album = tmp_path / "album"
    album.mkdir()
    track.path.rename(album / track.path.name)
    output = tmp_path / "output"
    output.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (output / "album").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symbolic links are unavailable")
    lookup = Mock(return_value=sync.Lyrics("hello\n", False))
    monkeypatch.setattr(sync, "_lookup", lookup)
    assert sync.run(tmp_path, output=output, embed=False, dry_run=False) == 1
    lookup.assert_not_called()
    assert not list(outside.iterdir())


def test_non_json_response(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sync, "urlopen", Mock(return_value=_Response(b"html", "text/html")))
    with pytest.raises(ValueError, match="non-JSON"):
        sync._lookup(track)


def test_batch_spacing(track: sync.Track, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    second = tmp_path / "second.flac"
    second.write_bytes(track.path.read_bytes())
    lookup = Mock(return_value=sync.Lyrics("hello\n", False))
    delay = Mock()
    monkeypatch.setattr(sync, "_lookup", lookup)
    monkeypatch.setattr(sync, "sleep", delay)
    assert sync.run(tmp_path, output=None, embed=False, dry_run=False) == 0
    assert lookup.call_count == 2
    delay.assert_called_once_with(0.75)


def test_lookup_without_album(track: sync.Track, monkeypatch: pytest.MonkeyPatch) -> None:
    track = replace(track, album="")
    response = _Response(json.dumps(_record(track)).encode())
    lookup = Mock(return_value=response)
    monkeypatch.setattr(sync, "urlopen", lookup)
    assert sync._lookup(track) is not None
    request = lookup.call_args.args[0]
    assert "album_name" not in request.full_url
    assert "duration=1" in request.full_url


@pytest.mark.parametrize("flag", ["-y", "--yes"])
def test_cli_yes(track: sync.Track, monkeypatch: pytest.MonkeyPatch, flag: str) -> None:
    target = track.path.with_suffix(".lrc")
    old = "[00:00.00] old\n"
    lyrics = sync.Lyrics("[00:00.00] new\n", True)
    target.write_text(old, encoding="utf-8")
    monkeypatch.setattr(sync, "_lookup", Mock(return_value=lyrics))
    monkeypatch.setattr(sync.sys.stdin, "isatty", lambda: False)
    prompt = Mock(side_effect=AssertionError("unexpected prompt"))
    monkeypatch.setattr("builtins.input", prompt)
    args = ["lyrics-sync", str(track.path), flag]
    assert main([*args, "--dry-run"]) == 0
    assert target.read_text(encoding="utf-8") == old
    assert main(args) == 0
    assert target.read_text(encoding="utf-8") == lyrics.text
    assert main(args) == 0
    prompt.assert_not_called()
    monkeypatch.setattr(sync, "_lookup", Mock(return_value=sync.Lyrics("plain\n", False)))
    assert main(args) == 0
    assert target.read_text(encoding="utf-8") == lyrics.text
    assert not track.path.with_suffix(".txt").exists()


def test_cli_recursion(track: sync.Track, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    album = tmp_path / "album"
    album.mkdir()
    nested = album / track.path.name
    nested.write_bytes(track.path.read_bytes())
    lookup = Mock(return_value=sync.Lyrics("hello\n", False))
    monkeypatch.setattr(sync, "_lookup", lookup)
    args = ["lyrics-sync", str(tmp_path), "--dry-run"]
    assert main([*args, "--no-recursive"]) == 0
    assert lookup.call_count == 1
    lookup.reset_mock()
    assert main([*args, "--recursive"]) == 0
    assert lookup.call_count == 2
    assert not list(tmp_path.rglob("*.txt"))
