"""Personal top artists and tracks from Spotify's affinity lists."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, TypeAlias

from .client import AsyncClient
from .library_models import track_from_data
from .playback import integer, mapping, records
from .query import QueryClient
from .session import AuthSession
from .specialized.data_wrappers import Artist, Track, from_dict
from .types import BaseClientError

TimeRange: TypeAlias = Literal["short_term", "medium_term", "long_term"]


@dataclass(frozen=True, slots=True)
class TopContent:
    artists: tuple[Artist, ...]
    tracks: tuple[Track, ...]
    total_artists: int
    total_tracks: int


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
        """Fetch top artists and tracks together for a chosen affinity range."""
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
        response = await self.queries.pathfinder_query(variables, "userTopContent", max_attempts=1)
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
