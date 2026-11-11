"""Run ``python examples/taste.py`` with SPOTIFY_COOKIE in your environment."""

import asyncio
import os

from rich.console import Console
from rich.table import Table

from spotapi import AsyncClient, ListeningStats


async def main() -> None:
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        favorites = await ListeningStats(client).get(time_range="medium_term", limit=10)

    table = Table(title="Your last six months", border_style="green")
    table.add_column("#", justify="right", style="dim")
    table.add_column("Track", style="bold")
    table.add_column("Artist", style="cyan")
    for rank, track in enumerate(favorites.tracks, start=1):
        artists = track.artists.items if track.artists else ()
        names = ", ".join(artist.profile.name for artist in artists if artist.profile)
        table.add_row(str(rank), track.name, names)

    Console().print(table)


if __name__ == "__main__":
    asyncio.run(main())
