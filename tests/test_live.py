"""Opt-in integration tests against Spotify's live public web catalogue."""

from __future__ import annotations

import asyncio
from typing import cast

import pytest

from spotapi.models.catalogue import (
    AlbumDetails,
    ArtistDetails,
    TrackDetails,
)
from spotapi.public import Public

pytestmark = pytest.mark.live


@pytest.mark.parametrize("query", ("Daft Punk", "Taylor Swift", "Radiohead"))
def test_live_search_returns_tracks_artists_and_albums(query: str) -> None:
    """Search Spotify and validate the actual search-result model fields."""

    async def scenario() -> None:
        results = await Public.search(
            query,
            types=("track", "artist", "album"),
            limit=5,
        )

        assert results.query == query
        assert results.requested_types == ("track", "artist", "album")
        assert results.tracks, f"Spotify returned no tracks for {query!r}"
        assert results.artists, f"Spotify returned no artists for {query!r}"
        assert results.albums, f"Spotify returned no albums for {query!r}"

        assert all(item.id and item.name and item.uri for item in results.tracks)
        assert all(item.id and item.name and item.uri for item in results.artists)
        assert all(item.id and item.name and item.uri for item in results.albums)

    asyncio.run(scenario())


def test_live_get_exact_track_from_shared_url() -> None:
    """Resolve a Spotify share URL including its ``si`` tracking parameter."""

    shared_url = "https://open.spotify.com/track/39MK3d3fonIP8Mz9oHCTBB?si=765229d9bcf4459f"

    async def scenario() -> None:
        track = await Public.get(shared_url)

        details = cast(TrackDetails, track)

        assert details.id == "39MK3d3fonIP8Mz9oHCTBB"
        assert details.uri == "spotify:track:39MK3d3fonIP8Mz9oHCTBB"
        assert details.name

    asyncio.run(scenario())


def test_live_get_track_artist_and_album_from_search() -> None:
    """Round-trip real search hits through the resource detail lookups."""

    async def scenario() -> None:
        results = await Public.search(
            "Daft Punk",
            types=("track", "artist", "album"),
            limit=5,
        )

        assert results.tracks and results.artists and results.albums

        track, artist, album = await asyncio.gather(
            Public.get(results.tracks[0].uri),
            Public.get(results.artists[0].uri),
            Public.get(results.albums[0].uri),
        )

        print(track, artist, album)

        track_details = cast(TrackDetails, track)
        artist_details = cast(ArtistDetails, artist)
        album_details = cast(AlbumDetails, album)

        assert track_details.id == results.tracks[0].id
        assert artist_details.id == results.artists[0].id
        assert album_details.id == results.albums[0].id
        assert track_details.name and artist_details.profile.name and album_details.name

    asyncio.run(scenario())


def test_live_search_accepts_plural_category_alias() -> None:
    """Accept plural aliases and return only the requested category."""

    async def scenario() -> None:
        results = await Public.search("Daft Punk", types="artists", limit=3)

        assert results.artists
        assert not results.tracks
        assert all(item.name and item.id and item.uri for item in results.artists)

    asyncio.run(scenario())
