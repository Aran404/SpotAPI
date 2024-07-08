from spotify.playlist import PrivatePlaylist, Login, BaseClient, PublicPlaylist
from typing import Optional, Mapping, Any, List, Tuple
from spotify.exceptions import SongError
from spotify.http.request import TLSClient


class Song(BaseClient):
    """
    Extends the PrivatePlaylist class with methods that can only be used while logged in.
    These methods interact with songs and tend to be used in the context of a playlist.
    """

    def __init__(
        self,
        playlist: Optional[PrivatePlaylist] = None,
        *,
        client: Optional[TLSClient] = TLSClient("chrome_120", "", auto_retries=3),
    ) -> None:
        self.playlist = playlist
        super().__init__(client=playlist.client if playlist else client)

    def query_songs(self, query: str, limit: Optional[int] = 10) -> Mapping[str, Any]:
        """
        Searches for songs in the spotify catalog.
        """
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "searchDesktop",
            "variables": '{"searchTerm":"'
            + query
            + '","offset":0,"limit":'
            + str(limit)
            + ',"numberOfTopResults":5,"includeAudiobooks":true,"includeArtistHasConcertsField":false,"includePreReleases":true,"includeLocalConcertsField":false}',
            "extensions": '{"persistedQuery":{"version":1,"sha256Hash":"'
            + self.part_hash("searchDesktop")
            + '"}}',
        }

        resp = self.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise SongError("Could not get songs", error=resp.error.string)

        return resp.response

    def add_song_to_playlist(self, song_id: str) -> None:
        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        if "track" in song_id:
            song_id = song_id.split("track/")[1]

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = {
            "variables": {
                "uris": ["spotify:track:" + song_id],
                "playlistUri": "spotify:playlist:" + self.playlist.playlist_id,
                "newPosition": {"moveType": "BOTTOM_OF_PLAYLIST", "fromUid": None},
            },
            "operationName": "addToPlaylist",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.part_hash("addToPlaylist"),
                }
            },
        }
        resp = self.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError("Could not add song to playlist", error=resp.error.string)

    def __stage_remove_song(self, uids: List[str]) -> None:
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = {
            "variables": {
                "playlistUri": "spotify:playlist:" + self.playlist.playlist_id,
                "uids": uids,
            },
            "operationName": "removeFromPlaylist",
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.part_hash("removeFromPlaylist"),
                }
            },
        }
        resp = self.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise SongError(
                "Could not remove song from playlist", error=resp.error.string
            )
            
    def __parse_playlist_items(
        self, 
        items: List[Mapping[str, Any]],
        song_id: Optional[str] = None,
        song_name: Optional[str] = None,
        all_instances: Optional[bool] = False,
    ) -> Tuple[List[str], bool]:
        uids: List[str] = []
        for item in items:
            is_song_id = song_id and song_id in item["itemV2"]["data"]["uri"]
            is_song_name = song_name and song_name.lower() in str(item["itemV2"]["data"]["name"]).lower()

            if is_song_id or is_song_name:
                uids.append(item["uid"])

                if all_instances:
                    return uids, True
                
        return uids, False

    def remove_song_from_playlist(
        self,
        *,
        song_id: Optional[str] = None,
        song_name: Optional[str] = None,
        all_instances: Optional[bool] = False,
    ) -> None:
        """
        Removes a song from the playlist.
        If all_instances is True, only song_name can be used.
        """
        if not (song_id or song_name):
            raise ValueError("Must provide either song_id or song_name")

        if all_instances and song_id:
            raise ValueError("Cannot provide both song_id and all_instances")

        if not self.playlist or not hasattr(self.playlist, "playlist_id"):
            raise ValueError("Playlist not set")

        playlist = PublicPlaylist(self.playlist.playlist_id).paginate_playlist()
        
        uids: List[str] = []
        for playlist_chunk in playlist:
            items = playlist_chunk["data"]["playlistV2"]["content"]["items"]
            extended_uids, stop = self.__parse_playlist_items(
                items, song_id=song_id, song_name=song_name, all_instances=all_instances
            )
            uids.extend(extended_uids)
            
            if stop:
                break

        if len(uids) == 0:
            raise SongError("Song not found in playlist")

        self.__stage_remove_song(uids)
