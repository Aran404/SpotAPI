"""Personal top artists and tracks from Spotify's affinity lists."""

from __future__ import annotations

from typing import Any

from spotapi.models.library import track_from_data

from ._parsing import integer, mapping, records
from .client import AsyncClient
from .models.catalogue import Artist, Track, from_dict
from .models.stats import TimeRange, TopContent
from .operations import Operations
from .query import QueryClient
from .session import AuthSession
from .types import BaseClientError


class ListeningStats:
    """Get both rankings in one request with ``await stats.get()``."""

    __slots__ = ("queries",)

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow an authenticated client for Spotify affinity rankings."""
        session = client.session if isinstance(client, AsyncClient) else client
        self.queries = QueryClient(session)

    async def get(
        self,
        *,
        time_range: TimeRange = "short_term",
        limit: int = 20,
        offset: int = 0,
        artists: bool = True,
        tracks: bool = True,
    ) -> TopContent:
        """Read Spotify's affinity rankings for the current account.

        Args:
            time_range: short_term, medium_term or long_term ranking window.
            limit: Requested size of each ranking page, from 1 to 50.
            offset: Nonnegative index of the first requested entry.
            artists: Include artist rankings.
            tracks: Include track rankings; at least one ranking must be enabled.

        Returns:
            Both requested rankings and their reported totals in one response.

        These are affinity rankings, not measured listening counts.
        """
        if time_range not in {"short_term", "medium_term", "long_term"}:
            raise ValueError("Choose short_term, medium_term or long_term")
        if type(limit) is not int or not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        if not artists and not tracks:
            raise ValueError("Request artists, tracks or both")

        affinity = {
            "offset": offset,
            "limit": limit,
            "sortBy": "AFFINITY",
            "timeRange": "MID_TERM" if time_range == "medium_term" else time_range.upper(),
        }
        variables: dict[str, Any] = {
            "includeTopArtists": artists,
            "topArtistsInput": affinity,
            "includeTopTracks": tracks,
            "topTracksInput": affinity,
        }
        response = await self.queries.pathfinder_query(variables, Operations.USER_TOP_CONTENT)
        profile = mapping(mapping(response.get("me")).get("profile"))
        artist_page = mapping(profile.get("topArtists"))
        track_page = mapping(profile.get("topTracks"))
        for requested, page in ((artists, artist_page), (tracks, track_page)):
            if requested and not isinstance(page.get("items"), list):
                raise BaseClientError("Spotify returned no top-content list")

        return TopContent(
            tuple(
                from_dict(Artist, data)
                for row in records(artist_page.get("items"))
                if (data := mapping(row.get("data"))).get("uri")
            ),
            tuple(
                track_from_data(data)
                for row in records(track_page.get("items"))
                if (data := mapping(row.get("data"))).get("uri")
            ),
            integer(artist_page.get("totalCount")),
            integer(track_page.get("totalCount")),
        )

    async def top_tracks(
        self, *, time_range: TimeRange = "short_term", limit: int = 20, offset: int = 0
    ) -> tuple[Track, ...]:
        """Read top tracks for short_term, medium_term or long_term affinity."""
        result = await self.get(time_range=time_range, limit=limit, offset=offset, artists=False)
        return result.tracks

    async def top_artists(
        self, *, time_range: TimeRange = "short_term", limit: int = 20, offset: int = 0
    ) -> tuple[Artist, ...]:
        """Read top artists for short_term, medium_term or long_term affinity."""
        result = await self.get(time_range=time_range, limit=limit, offset=offset, tracks=False)
        return result.artists
