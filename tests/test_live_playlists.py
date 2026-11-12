"""Explicit temporary-playlist mutations with unconditional cleanup."""

import asyncio
import os
from io import BytesIO

import pytest

from spotapi import AsyncClient, Library, LikedTracks, Playlist, PlaylistHandler
from spotapi.datastruct import ObjectDict
from spotapi.playlist import _PLAYLIST_URL

pytestmark = [pytest.mark.live, pytest.mark.authenticated, pytest.mark.mutates]


async def wait_for_playlist_count(playlist: Playlist, count: int) -> None:
    """Poll reads for propagation; never retry a mutation or accept an error union."""
    async with asyncio.timeout(15):
        while True:
            data = await playlist.ph.qc.pathfinder_query(
                {
                    "uri": playlist.playlist_id,
                    "offset": 0,
                    "limit": 100,
                    "includeEpisodeContentRatingsV2": True,
                },
                "fetchPlaylistContents",
            )
            root = data.get("playlistV2")
            assert isinstance(root, ObjectDict)
            assert root.get("__typename") in {"Playlist", "NotFound"}
            if root.get("__typename") == "Playlist":
                content = root.get("content")
                assert isinstance(content, ObjectDict)
                if content.get("totalCount") == count:
                    return
            await asyncio.sleep(1)


async def test_live_playlist_metadata_and_exact_duplicate_removal() -> None:
    """Verify edits and occurrence removal on a new temporary playlist, then remove it."""
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        playlist = await PlaylistHandler(client).create_playlist("SpotAPI temporary beta test")
        try:
            await playlist.edit(name="SpotAPI verified metadata", description="Temporary test")
            details = await playlist.get(fresh=True)
            assert details.name == "SpotAPI verified metadata"
            assert details.description == "Temporary test"
            await playlist.edit(description="")
            assert (await playlist.get(fresh=True)).description == ""
            await playlist.set_published(False)

            track = "33XUHrCbrAW6me9ewdCZip"
            await wait_for_playlist_count(playlist, 0)
            await Library(client).pin(playlist.playlist_id)
            await Library(client).unpin(playlist.playlist_id)
            await playlist.add_tracks(track, track)
            await wait_for_playlist_count(playlist, 2)
            entries = [entry async for entry in playlist.items()]
            assert len(entries) == 2 and entries[0].uid != entries[1].uid
            await playlist.move_occurrences(entries[1], before=entries[0])
            async with asyncio.timeout(15):
                while [entry.uid async for entry in playlist.items()] != [
                    entries[1].uid,
                    entries[0].uid,
                ]:
                    await asyncio.sleep(1)
            await playlist.remove_occurrences(entries[1])
            await wait_for_playlist_count(playlist, 1)
            remaining = [entry async for entry in playlist.items()]
            assert len(remaining) == 1 and remaining[0].uid == entries[0].uid
        finally:
            await playlist.delete()


async def test_live_playlist_cover_upload_and_clear() -> None:
    image = pytest.importorskip("PIL.Image")
    buffer = BytesIO()
    image.new("RGB", (300, 300), "#246e83").save(buffer, "JPEG")

    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        playlist = await PlaylistHandler(client).create_playlist("SpotAPI temporary cover test")

        async def cover() -> object:
            url = f"{_PLAYLIST_URL}/{playlist.playlist_id.rsplit(':', 1)[-1]}"
            response = await client.get(
                url,
                authorized=True,
                headers={"accept": "application/json"},
                max_attempts=1,
            )
            assert response.json is not None, (
                "Playlist metadata was not a JSON object; "
                f"content-type={response.headers.get('content-type')!r}"
            )
            return response.json["attributes"].get("picture")

        try:
            await playlist.set_cover(buffer.getvalue())
            picture = await cover()
            assert isinstance(picture, str) and picture
            await playlist.set_cover(None)
            assert not await cover()
        finally:
            await playlist.delete()


async def test_live_saved_track_changes_restore_original_unsaved_state() -> None:
    """Use an unsaved candidate so existing saved dates and ordering remain intact."""
    async with await AsyncClient.from_cookies(os.environ["SPOTIFY_COOKIE"]) as client:
        liked = LikedTracks(client)
        candidates = ["39MK3d3fonIP8Mz9oHCTBB", "33XUHrCbrAW6me9ewdCZip"]
        flags = await liked.contains(candidates)
        track = next(
            (uri for uri, saved in zip(candidates, flags, strict=True) if not saved), None
        )
        if track is None:
            pytest.skip("Both candidates are already saved; preserve their original saved dates")
        try:
            await liked.add([track])
            assert await liked.contains([track]) == (True,)
        finally:
            await liked.remove([track])
            assert await liked.contains([track]) == (False,)
