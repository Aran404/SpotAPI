from __future__ import annotations

import json
import re
import time
from typing import Any, Generator, Mapping, Optional

from spotify.exceptions import PlaylistError
from spotify.http.request import TLSClient
from spotify import Login, BaseClient, User


class PublicPlaylist(BaseClient):
    """
    Allows you to get all public information on a playlist.
    No login is required.
    """

    def __init__(
        self,
        playlist: Optional[str] = None,
        /,
        client: Optional[TLSClient] = TLSClient("chrome_120", "", auto_retries=3),
    ) -> None:
        super().__init__(client=client)

        if playlist:
            self.playlist_id = (
                playlist.split("playlist/")[-1] if "playlist" in playlist else playlist
            )
            self.playlist_link = f"https://open.spotify.com/playlist/{self.playlist_id}"

    def get_playlist_info(
        self, limit: Optional[int] = 25, *, offset: Optional[int] = 0
    ) -> Mapping[str, Any]:
        """Gets the public playlist information"""
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "fetchPlaylist",
            "variables": json.dumps(
                {
                    "uri": f"spotify:playlist:{self.playlist_id}",
                    "offset": offset,
                    "limit": limit,
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.part_hash("fetchPlaylist"),
                    }
                }
            ),
        }

        resp = self.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise PlaylistError("Could not get playlist info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise PlaylistError("Invalid JSON")

        return resp.response

    def paginate_playlist(self) -> Generator[Mapping[str, Any], None, None]:
        """
        Generator that fetches playlist information in chunks

        Note: If total_tracks <= 353, then there is no need to paginate
        """
        UPPER_LIMIT: int = 353
        # We need to get the total songs first
        playlist = self.get_playlist_info(limit=UPPER_LIMIT)
        total_count: int = playlist["data"]["playlistV2"]["content"]["totalCount"]

        yield playlist["data"]["playlistV2"]["content"]

        if total_count <= UPPER_LIMIT:
            return

        offset = UPPER_LIMIT
        while offset < total_count:
            yield self.get_playlist_info(limit=UPPER_LIMIT, offset=offset)["data"][
                "playlistV2"
            ]["content"]
            offset += UPPER_LIMIT


class PrivatePlaylist(BaseClient, Login):
    """
    Methods on playlists that you can only do whilst logged in.
    """

    def __new__(
        cls,
        login: Login,
        playlist: Optional[str] = None,
    ) -> PrivatePlaylist:
        instance = super().__new__(cls)
        instance.__dict__ = login.__dict__.copy()
        return instance

    def __init__(
        self,
        login: Login,
        playlist: Optional[str] = None,
    ) -> None:
        if not login.logged_in:
            raise ValueError("Must be logged in")

        if playlist:
            self.playlist_id = (
                playlist.split("playlist/")[-1] if "playlist" in playlist else playlist
            )

        super().__init__(client=login.client)

        self.user = User(login)
        # We need to check if a user can use a method
        self._playlist: bool = bool(playlist)

    def set_playlist(self, playlist: str) -> None:
        if "playlist:" in playlist:
            playlist = playlist.split("playlist:")[-1]

        if hasattr(playlist, "playlist_id"):
            self.playlist_id = playlist

        setattr(self, "playlist_id", playlist)
        self._playlist = True

    def add_to_library(self) -> None:
        """Adds the playlist to your library"""
        if not self._playlist:
            raise ValueError("Playlist not set")

        url = f"https://spclient.wg.spotify.com/playlist/v2/user/{self.user.username}/rootlist/changes"
        payload = {
            "deltas": [
                {
                    "ops": [
                        {
                            "kind": 2,
                            "add": {
                                "items": [
                                    {
                                        "uri": f"spotify:playlist:{self.playlist_id}",
                                        "attributes": {
                                            "timestamp": int(time.time()),
                                            "formatAttributes": [],
                                            "availableSignals": [],
                                        },
                                    }
                                ],
                                "addFirst": True,
                            },
                        }
                    ],
                    "info": {"source": {"client": 5}},
                }
            ],
            "wantResultingRevisions": False,
            "wantSyncResult": False,
            "nonces": [],
        }

        resp = self.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise PlaylistError(
                "Could not add playlist to library", error=resp.error.string
            )

    def remove_from_library(self) -> None:
        """Removes the playlist from your library"""
        if not self._playlist:
            raise ValueError("Playlist not set")

        url = f"https://spclient.wg.spotify.com/playlist/v2/user/{self.user.username}/rootlist/changes"
        payload = {
            "deltas": [
                {
                    "ops": [
                        {
                            "kind": 3,
                            "rem": {
                                "items": [
                                    {"uri": f"spotify:playlist:{self.playlist_id}"}
                                ],
                                "itemsAsKey": True,
                            },
                        }
                    ],
                    "info": {"source": {"client": 5}},
                }
            ],
            "wantResultingRevisions": False,
            "wantSyncResult": False,
            "nonces": [],
        }

        resp = self.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise PlaylistError(
                "Could not remove playlist from library", error=resp.error.string
            )

    def delete_playlist(self) -> None:
        """Deletes the playlist from your library"""

        # They are the same requests
        return self.remove_from_library()

    def get_library(self, limit: Optional[int] = 50) -> Mapping[str, Any]:
        """Gets all the playlists in your library"""
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "libraryV3",
            "variables": json.dumps(
                {
                    "filters": [],
                    "order": None,
                    "textFilter": "",
                    "features": ["LIKED_SONGS", "YOUR_EPISODES", "PRERELEASES"],
                    "limit": limit,
                    "offset": 0,
                    "flatten": False,
                    "expandedFolders": [],
                    "folderUri": None,
                    "includeFoldersWhenFlattening": True,
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.part_hash("libraryV3"),
                    }
                }
            ),
        }

        resp = self.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise PlaylistError("Could not get library", error=resp.error.string)

        return resp.response

    def __stage_create_playlist(self, name: str) -> str:
        url = "https://spclient.wg.spotify.com/playlist/v2/playlist"
        payload = {
            "ops": [
                {
                    "kind": 6,
                    "updateListAttributes": {
                        "newAttributes": {
                            "values": {
                                "name": name,
                                "formatAttributes": [],
                                "pictureSize": [],
                            },
                            "noValue": [],
                        }
                    },
                }
            ]
        }

        resp = self.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise PlaylistError(
                "Could not stage create playlist", error=resp.error.string
            )

        pattern = r"spotify:playlist:[a-zA-Z0-9]+"
        matched = re.search(pattern, resp.response)

        if not matched:
            raise PlaylistError("Could not find desired playlist ID")

        return matched.group(0)

    def create_playlist(self, name: str) -> str:
        """Creates a new playlist"""
        playlist_id = self.__stage_create_playlist(name)
        url = f"https://spclient.wg.spotify.com/playlist/v2/user/{self.user.username}/rootlist/changes"
        payload = {
            "deltas": [
                {
                    "ops": [
                        {
                            "kind": 2,
                            "add": {
                                "items": [
                                    {
                                        "uri": playlist_id,
                                        "attributes": {
                                            "timestamp": int(time.time()),
                                            "formatAttributes": [],
                                            "availableSignals": [],
                                        },
                                    }
                                ],
                                "addFirst": True,
                            },
                        }
                    ],
                    "info": {"source": {"client": 5}},
                }
            ],
            "wantResultingRevisions": False,
            "wantSyncResult": False,
            "nonces": [],
        }

        resp = self.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise PlaylistError("Could not create playlist", error=resp.error.string)

        return playlist_id
