"""Inspect a public playlist's tempo and harmonic keys, when Spotify supplies them."""

import asyncio

from rich.console import Console
from rich.table import Table

from spotapi import Public


async def main() -> None:
    uri = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"

    playlist = await Public.get_playlist(uri)

    table = Table(title=playlist.name, header_style="bold green")

    for heading in ("Track", "BPM", "Camelot key"):
        table.add_column(heading)

    async for tracks in Public.get_playlist_tracks(uri):
        for track in tracks:
            tempo = f"{track.bpm:.0f}" if track.bpm is not None else "—"

            table.add_row(track.name, tempo, track.camelot_key or "—")

    Console().print(table)


if __name__ == "__main__":
    asyncio.run(main())
