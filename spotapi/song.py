import json
from collections.abc import Mapping, Iterable, Generator
from typing import Any, List, Tuple

from spotapi.types.annotations import enforce
from spotapi.exceptions import SongError
from spotapi.http.request import TLSClient
from spotapi.client import BaseClient
from spotapi.playlist import PrivatePlaylist, PublicPlaylist

__all__ = ["Song", "SongError"]


@enforce
class Song:
    """
    Extends the PrivatePlaylist class with methods that can only be used while logged in.
    These methods interact with songs and tend to be used in the context of a playlist.
    """

    __slots__ = (
        "playlist",
        "base",
    )

    def __init__(
        self,
        playlist: PrivatePlaylist | None = None,
        *,
        client: TLSClient = TLSClient("chrome_120", "", auto_retries=3),
    ) -> None:
        self.playlist = playlist
        self.base = BaseClient(client=playlist.login.client if playlist else client)

    def query_songs(
        self, query: str, /, limit: int = 10, *, offset: int = 0
    ) -> Mapping[str, Any]:
        """
        Searches for songs in the Spotify catalog.
        NOTE: Returns the raw result unlike paginate_songs which only returns the songs.
        """
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "searchDesktop",
            "variables": json.dumps(
                {
                    "searchTerm": query,
                    "offset": offset,
                    "limit": limit,
                    "numberOfTopResults": 5,
                    "includeAudiobooks": True,
                    "includeArtistHasConcertsField": False,
                    "includePreReleases": True,
                    "includeLocalConcertsField": False,
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.base.part_hash("searchDesktop"),
                    }
                }
            ),
        }

        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise SongError("Could not get songs", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise SongError("Invalid JSON")

        return resp.response

    def paginate_songs(self, query: str, /) -> Generator[Mapping[str, Any], None, None]:
        """
        Generator that fetches songs in chunks

        Note: If total_tracks <= 100, then there is no need to paginate
        """
        UPPER_LIMIT: int = 100
        # We need to get the total songs first
        songs = self.query_songs(query, limit=UPPER_LIMIT)
        total_count: int = songs["data"]["searchV2"]["tracksV2"]["totalCount"]

        yield songs["data"]["searchV2"]["tracksV2"]["items"]

        if total_count <= UPPER_LIMIT:
            return

        offset = UPPER_LIMIT
        while offset < total_count:
            yield self.query_songs(query, limit=UPPER_LIMIT, offset=offset)["data"][
                "searchV2"
            ]["tracksV2"]["items"]
            offset += UPPER_LIMIT

    def add_song_to_playlist(self, song_id: str, /) -> None:
        """Adds a song to the playlist"""
        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        if "track" in song_id:
            song_id = song_id.split("track/")[1]

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = {
            "variables": {
                "uris": [f"spotify:track:{song_id}"],
                "playlistUri": f"spotify:playlist:{self.playlist.playlist_id}",
                "newPosition": {"moveType": "BOTTOM_OF_PLAYLIST", "fromUid": None},
            },
            "operationName": "addToPlaylist",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.base.part_hash("addToPlaylist"),
                }
            },
        }
        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError("Could not add song to playlist", error=resp.error.string)

    def _stage_remove_song(self, uids: List[str]) -> None:
        # If None, something internal went wrong
        assert self.playlist is not None, "Playlist not set"

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = {
            "variables": {
                "playlistUri": f"spotify:playlist:{self.playlist.playlist_id}",
                "uids": uids,
            },
            "operationName": "removeFromPlaylist",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.base.part_hash("removeFromPlaylist"),
                }
            },
        }

        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError(
                "Could not remove song from playlist", error=resp.error.string
            )

    @staticmethod
    def parse_playlist_items(
        items: Iterable[Mapping[str, Any]],
        *,
        song_id: str | None = None,
        song_name: str | None = None,
        all_instances: bool = False,
    ) -> Tuple[List[str], bool]:
        uids: List[str] = []
        for item in items:
            is_song_id = song_id and song_id in item["itemV2"]["data"]["uri"]
            is_song_name = (
                song_name
                and song_name.lower() in str(item["itemV2"]["data"]["name"]).lower()
            )

            if is_song_id or is_song_name:
                uids.append(item["uid"])

                if all_instances:
                    return uids, True

        return uids, False

    def remove_song_from_playlist(
        self,
        *,
        all_instances: bool = False,
        uid: str | None = None,
        song_id: str | None = None,
        song_name: str | None = None,
    ) -> None:
        """
        Removes a song from the playlist.
        If all_instances is True, only song_name can be used.
        """
        if song_id and "track" in song_id:
            song_id = song_id.split("track:")[1]

        if not (song_id or song_name or uid):
            raise ValueError("Must provide either song_id or song_name or uid")

        if all_instances and song_id:
            raise ValueError("Cannot provide both song_id and all_instances")

        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        playlist = PublicPlaylist(self.playlist.playlist_id).paginate_playlist()

        uids: List[str] = []
        if not uid:
            for playlist_chunk in playlist:
                items = playlist_chunk["items"]
                extended_uids, stop = Song.parse_playlist_items(
                    items,
                    song_id=song_id,
                    song_name=song_name,
                    all_instances=all_instances,
                )
                uids.extend(extended_uids)

                if stop:
                    playlist.close()
                    break
        else:
            uids.append(uid)

        if len(uids) == 0:
            raise SongError("Song not found in playlist")

        self._stage_remove_song(uids)

    def like_song(self, song_id: str, /) -> None:
        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        if song_id and "track" in song_id:
            song_id = song_id.split("track:")[1]

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = {
            "variables": {"uris": [f"spotify:track:{song_id}"]},
            "operationName": "addToLibrary",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.base.part_hash("addToLibrary"),
                }
            },
        }

        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError("Could not like song", error=resp.error.string)
