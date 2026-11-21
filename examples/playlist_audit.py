"""Audit a public playlist and export its entries to CSV without a developer key.

Run from the repository root after installing SpotAPI::

    python examples/playlist_audit.py PLAYLIST_URL --output playlist.csv

Only analyse playlists you are permitted to access. Playlist reads use the
library's ordinary pagination and respect upstream failures (no bypasses).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import os
from collections.abc import AsyncGenerator
from contextlib import aclosing
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile

from spotapi import Public
from spotapi.models.catalogue.playlist_details import PlaylistEntry
from spotapi.models.catalogue.playlist_track import PlaylistTrack

_COLUMNS = (
    "position",
    "occurrence_id",
    "kind",
    "spotify_uri",
    "name",
    "artists",
    "duration_ms",
    "added_at",
    "duplicate",
)


@dataclass(slots=True)
class AuditSummary:
    scanned: int = 0
    tracks: int = 0
    unique_tracks: int = 0
    repeated_tracks: int = 0
    episodes: int = 0
    unavailable: int = 0


async def export_playlist(
    entries: AsyncGenerator[PlaylistEntry, None],
    output: Path,
    *,
    max_items: int = 10_000,
) -> AuditSummary:
    """Stream up to max_items playlist occurrences into an atomic CSV export.

    Each occurrence gets its own row, so repeated track URIs are preserved.
    A failed read leaves no misleading partial output file.
    """
    if not 1 <= max_items <= 10_000:
        raise ValueError("max_items must be between 1 and 10,000")
    if output.exists():
        raise FileExistsError(f"Refusing to replace existing file: {output}")

    seen: set[str] = set()
    summary = AuditSummary()
    temp_path: Path | None = None

    try:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=output.parent,
            prefix=f".{output.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temp_path = Path(stream.name)
            writer = csv.DictWriter(stream, fieldnames=_COLUMNS)
            writer.writeheader()

            async with aclosing(entries) as iterator:
                while summary.scanned < max_items:
                    entry = await anext(iterator, None)
                    if entry is None:
                        break

                    summary.scanned += 1
                    item = entry.item
                    kind = "unavailable"
                    duplicate = False
                    artists = ""
                    duration = ""

                    if isinstance(item, PlaylistTrack):
                        kind = "track"
                        summary.tracks += 1
                        duplicate = item.uri in seen
                        if duplicate:
                            summary.repeated_tracks += 1
                        else:
                            seen.add(item.uri)
                        if item.artists is not None:
                            artists = ", ".join(
                                artist.profile.name
                                for artist in item.artists.items
                                if artist.profile is not None
                            )
                        if item.duration is not None:
                            duration = str(item.duration.total_milliseconds)
                    elif item is None:
                        summary.unavailable += 1
                    else:
                        kind = "episode"
                        summary.episodes += 1
                        if item.duration is not None:
                            duration = str(item.duration.total_milliseconds)

                    writer.writerow(
                        {
                            "position": summary.scanned,
                            "occurrence_id": entry.uid or "",
                            "kind": kind,
                            "spotify_uri": entry.uri or "",
                            "name": item.name if item is not None else "",
                            "artists": artists,
                            "duration_ms": duration,
                            "added_at": entry.added_at or "",
                            "duplicate": int(duplicate),
                        }
                    )

        summary.unique_tracks = len(seen)
        # Create a hard link in the same directory, without overwriting a file
        # created by another process during the export. os.replace is unsafe here.
        os.link(temp_path, output)
        return summary
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


def _max_items(value: str) -> int:
    try:
        count = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("expected an integer") from error
    if not 1 <= count <= 10_000:
        raise argparse.ArgumentTypeError("choose between 1 and 10,000")
    return count


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("playlist", help="Public Spotify playlist URL, URI, or ID")
    parser.add_argument("--output", required=True, type=Path, help="New output CSV file")
    parser.add_argument("--max-items", type=_max_items, default=10_000)
    args = parser.parse_args()

    summary = asyncio.run(
        export_playlist(
            Public.iter_playlist_items(args.playlist, limit=100),
            args.output,
            max_items=args.max_items,
        )
    )
    print(
        f"Scanned {summary.scanned:,} entries: {summary.tracks:,} tracks "
        f"({summary.unique_tracks:,} unique, {summary.repeated_tracks:,} repeated), "
        f"{summary.episodes:,} episodes, {summary.unavailable:,} unavailable."
    )
    print(f"CSV saved to {args.output}")


if __name__ == "__main__":
    main()
