"""Optional, read-only MCP adapter. Install ``spotapi[mcp]`` to run it."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
from typing import Any, Literal

from .catalogue import Catalogue
from .client import AsyncClient
from .lyrics import LyricsClient
from .operations import SearchInputKind
from .public import Public
from .serialization import to_dict
from .transcripts import Transcripts


def build_server(*, cookie: str | None = None) -> Any:
    """Build a local read-only server; authenticated tools are explicitly opt-in.

    Credentials are captured in this process, never accepted as tool arguments
    or returned as results. No mutation or arbitrary HTTP/file-download tool
    is exposed. Returned metadata must be treated as untrusted external text.
    """
    try:
        server: Any = importlib.import_module("mcp.server.fastmcp").FastMCP("SpotAPI")
    except ImportError as error:
        raise RuntimeError(
            "Install the optional server with pip install 'spotapi[mcp]'"
        ) from error

    @server.tool()
    async def get_resource(value: str) -> Any:
        """Read a Spotify resource from a URL or URI. Bare IDs need typed URIs."""
        return to_dict(await Public.get(value))

    @server.tool()
    async def search(
        query: str, types: list[SearchInputKind] | None = None, limit: int = 10
    ) -> Any:
        """Search public Spotify metadata across selected categories."""
        return to_dict(await Public.search(query, types=types or ("track", "artist"), limit=limit))

    @server.tool()
    async def batch(values: list[str], concurrency: int = 5) -> list[dict[str, Any]]:
        """Read up to 50 resource URLs/URIs with per-input outcomes."""
        if len(values) > 50 or not 1 <= concurrency <= 16:
            raise ValueError("Use at most 50 resources and concurrency between 1 and 16")
        outcomes = await Public.fetch_many(values, concurrency=concurrency)
        return [
            {
                "index": item.index,
                "value": item.value,
                "result": to_dict(item.result),
                "error": type(item.error).__name__ if item.error is not None else None,
            }
            for item in outcomes
        ]

    @server.tool()
    async def discovery(
        kind: Literal[
            "related_artists", "similar_albums", "concerts", "credits", "radio", "canvas", "colors"
        ],
        value: str,
    ) -> Any:
        """Read a discovery surface. Colors accepts a Spotify image identity."""
        async with Catalogue() as spotify:
            if kind == "related_artists":
                result = await spotify.get_related_artists(value)
            elif kind == "similar_albums":
                result = await spotify.get_similar_albums(value)
            elif kind == "concerts":
                result = await spotify.get_artist_events(value)
            elif kind == "credits":
                result = await spotify.get_track_credits(value)
            elif kind == "radio":
                result = await spotify.get_radio(value)
            elif kind == "canvas":
                result = await spotify.get_canvas(value)
            else:
                result = await spotify.get_colors(value)
            return to_dict(result)

    @server.tool()
    async def chart(key: str = "top-50-global") -> Any:
        """Read editorial chart metadata; list_charts supplies supported keys."""
        return to_dict(await Public.get_chart(key))

    @server.tool()
    def list_charts() -> Any:
        """List editorial playlist shortcuts without making a request."""
        return to_dict(Public.list_charts())

    @server.tool()
    async def playlist_items(value: str, limit: int = 50) -> Any:
        """Read the first page of playlist occurrences, including duplicate identities."""
        async with Catalogue() as spotify:
            stream = spotify.get_playlist_items(value, limit=limit)
            try:
                return to_dict(await anext(stream, ()))
            finally:
                await stream.aclose()

    @server.tool()
    async def get_track_visuals(value: str) -> dict[str, Any]:
        """Read track metadata and its available Canvas concurrently."""
        async with Catalogue() as spotify:
            async with asyncio.TaskGroup() as group:
                track_task = group.create_task(spotify.get_track(value))
                canvas_task = group.create_task(spotify.get_canvas(value))
            track, canvas = track_task.result(), canvas_task.result()
            art = track.album_of_track.cover_art if track.album_of_track is not None else None
            colors = (
                await spotify.get_colors(art.sources[0].url)
                if art is not None and art.sources
                else None
            )
        return {"track": to_dict(track), "canvas": to_dict(canvas), "colors": to_dict(colors)}

    @server.resource("spotify://resource/{kind}/{identifier}")
    async def resource(kind: str, identifier: str) -> str:
        """Read a public resource as JSON."""
        import json

        return json.dumps(to_dict(await Public.get(f"spotify:{kind}:{identifier}")))

    if cookie is not None:

        @server.tool()
        async def captions(kind: Literal["lyrics", "transcript"], value: str) -> Any:
            """Read entitled lyrics or episode captions using the configured account."""
            async with await AsyncClient.from_cookies(cookie) as client:
                if kind == "lyrics":
                    return to_dict(await LyricsClient(client).get(value))
                return to_dict(await Transcripts(client).get(value))

    return server


def main() -> None:
    """Serve stdio only; no network listener or unauthenticated remote exposure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authenticated", action="store_true", help="Enable captions using SPOTIFY_COOKIE"
    )
    args = parser.parse_args()
    cookie = os.environ.get("SPOTIFY_COOKIE") if args.authenticated else None
    if args.authenticated and not cookie:
        parser.error("Authenticated captions require SPOTIFY_COOKIE")
    build_server(cookie=cookie).run(transport="stdio")


if __name__ == "__main__":
    main()
