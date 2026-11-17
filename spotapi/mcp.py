"""Optional MCP adapter with public reads and explicitly enabled player controls."""

from __future__ import annotations

import argparse
import asyncio
import importlib
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, Literal

from .catalogue import Catalogue
from .client import AsyncClient
from .library import LikedTracks
from .lyrics import LyricsClient
from .operations import SearchInputKind
from .player import Player
from .public import Public
from .resources import parse_spotify_resource
from .serialization import to_dict
from .transcripts import Transcripts


def build_server(*, cookie: str | None = None, allow_player: bool = False) -> Any:
    """Build a local server with optional account and player tools.

    Credentials are captured in this process, never accepted as tool arguments
    or returned as results. Player controls require both allow_player and a
    cookie. Returned metadata must be treated as untrusted external text.
    """
    if allow_player and not cookie:
        raise ValueError("Player tools require a Spotify cookie")

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

    if allow_player and cookie is not None:
        _register_player_tools(server, cookie)

    return server


@asynccontextmanager
async def _player_session(cookie: str) -> AsyncGenerator[Player, None]:
    """Own the authentication and dealer connection for one player tool call."""
    completed = False
    try:
        async with (
            await AsyncClient.from_cookies(cookie) as client,
            Player(client).connect() as player,
        ):
            yield player
            completed = True
    except Exception as error:
        if completed:
            raise RuntimeError(
                "The operation completed, but connection cleanup failed. "
                "Check now_playing before repeating a playback or library change."
            ) from error

        raise


def _register_player_tools(server: Any, cookie: str) -> None:
    """Bind scoped account operations only after the host opts in."""
    annotations = importlib.import_module("mcp.types").ToolAnnotations
    read = annotations(readOnlyHint=True, openWorldHint=True)
    write = annotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False)

    @server.tool(annotations=read)
    async def now_playing() -> Any:
        """Read playback, available devices, and current music metadata."""
        async with _player_session(cookie) as player:
            return to_dict(
                {
                    "state": player.state,
                    "devices": player.devices,
                    "track_details": await player.current_track_details(),
                }
            )

    @server.tool(annotations=write)
    async def next() -> dict[str, bool]:
        """Skip to the next track on the active device."""
        async with _player_session(cookie) as player:
            await player.next()
        return {"completed": True}

    @server.tool(annotations=write)
    async def pause() -> dict[str, bool]:
        """Pause the active Spotify device."""
        async with _player_session(cookie) as player:
            await player.pause()
        return {"completed": True}

    @server.tool(annotations=write)
    async def resume() -> dict[str, bool]:
        """Resume the active Spotify device."""
        async with _player_session(cookie) as player:
            await player.resume()
        return {"completed": True}

    @server.tool(annotations=write)
    async def like(track: str | None = None) -> dict[str, bool]:
        """Save a supplied track, or the current music track, to Liked Songs."""
        if track is not None:
            uri = parse_spotify_resource(track, "track").uri
            async with await AsyncClient.from_cookies(cookie) as client:
                await LikedTracks(client).add([uri])
        else:
            async with _player_session(cookie) as player:
                await player.like()
        return {"completed": True}

    @server.tool(annotations=write)
    async def transfer(device_id: str, play: bool | None = None) -> dict[str, bool]:
        """Move playback to a full device ID returned by now_playing."""
        async with _player_session(cookie) as player:
            await player.transfer(device_id, play=play)
        return {"completed": True}


def main() -> None:
    """Serve stdio only; no network listener or unauthenticated remote exposure."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--authenticated", action="store_true", help="Enable captions using SPOTIFY_COOKIE"
    )
    parser.add_argument(
        "--allow-player",
        action="store_true",
        help="Enable now_playing and playback/library changes using SPOTIFY_COOKIE",
    )
    args = parser.parse_args()
    cookie = os.environ.get("SPOTIFY_COOKIE") if args.authenticated or args.allow_player else None
    if (args.authenticated or args.allow_player) and not cookie:
        parser.error("Account tools require SPOTIFY_COOKIE")
    build_server(cookie=cookie, allow_player=args.allow_player).run(transport="stdio")


if __name__ == "__main__":
    main()
