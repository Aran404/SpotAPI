"""Read-only contract checks for the public catalogue; no saved cookies."""

import asyncio
from contextlib import aclosing

import pytest

from spotapi import Public
from spotapi.models import PlaylistTrack

pytestmark = [pytest.mark.live]


@pytest.mark.parametrize("query", ["The Daily", "Dune"])
def test_live_extended_search_returns_typed_results(query: str) -> None:
    async def run() -> None:
        results = await Public.search(
            query, types=("audiobook", "episode", "user", "author", "genre"), limit=3
        )

        assert results.audiobooks and results.episodes and results.users and results.authors
        assert all(
            item.name and item.uri
            for item in (
                *results.audiobooks,
                *results.episodes,
                *results.users,
                *results.authors,
                *results.genres,
            )
        )

    asyncio.run(run())


def test_live_playlist_metadata_and_two_distinct_pages() -> None:
    async def run() -> None:
        uri = "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M"

        details = await Public.get_playlist(uri)

        assert details.name and details.total_count and details.uri == uri

        async with aclosing(Public.get_playlist_items(uri, limit=2)) as pages:
            first, second = await anext(pages), await anext(pages)

        assert len(first) == len(second) == 2
        assert [item.uid for item in first] != [item.uid for item in second]
        assert all(isinstance(item.item, PlaylistTrack) for item in (*first, *second))

        for entry in first:
            assert isinstance(entry.item, PlaylistTrack)
            assert entry.item.uri and entry.item.name

            if entry.item.bpm is not None:
                assert 0 < entry.item.bpm < 400

    asyncio.run(run())


def test_live_album_track_pagination_and_artist_release_pagination() -> None:
    async def run() -> None:
        async with aclosing(Public.get_album_tracks("4LH4d3cOWNNsVw41Gqt2kv", limit=2)) as pages:
            first, second = await anext(pages), await anext(pages)

        assert len(first) == len(second) == 2
        assert first[0].uri != second[0].uri

        async with aclosing(
            Public.get_artist_releases("4tZwfgrHOc3mvqYlEYSvVi", limit=2)
        ) as pages:
            first, second = await anext(pages), await anext(pages)

        assert first and second and first[0].uri != second[0].uri

    asyncio.run(run())


def test_live_credits_related_artists_and_profile() -> None:
    async def run() -> None:
        credits = await Public.get_track_credits("39MK3d3fonIP8Mz9oHCTBB")

        assert credits.contributors and all(credit.name for credit in credits.contributors)

        related = await Public.get_related_artists("4tZwfgrHOc3mvqYlEYSvVi")

        assert related and all(artist.name and artist.uri for artist in related)

        tracks = await Public.get_artist_top_tracks("4tZwfgrHOc3mvqYlEYSvVi")

        assert tracks and all(track.name and track.uri for track in tracks)

        profile = await Public.get_profile("https://open.spotify.com/user/spotify", limit=3)

        assert profile.uri == "spotify:user:spotify" and profile.name
        assert profile.public_playlists and len(profile.public_playlists) <= 3

    asyncio.run(run())


@pytest.mark.parametrize(
    "method",
    [
        "search_audiobooks",
        "search_episodes",
        "search_users",
        "search_authors",
        "search_genres",
    ],
)
def test_live_extended_page_helpers(method: str) -> None:
    async def run() -> None:
        async with aclosing(getattr(Public, method)("The Daily", limit=2)) as pages:
            items = await anext(pages)

        assert items and all(item.name and item.uri for item in items)

    asyncio.run(run())


def test_live_podcast_and_audiobook_metadata_have_distinct_models() -> None:
    from spotapi.models import Audiobook, PodcastDetails

    async def run() -> None:
        podcast = await Public.get_podcast("3IM0lmZxpFAY7CwMuv9H4g")

        book = await Public.get_audiobook("7iHfbu1YPACw6oZPAFJtqe")

        assert isinstance(podcast, PodcastDetails) and podcast.name
        assert isinstance(book, Audiobook) and book.authors_v2

    asyncio.run(run())
