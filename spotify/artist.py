from __future__ import annotations

import json
from typing import Any, Generator, Literal, Mapping, Optional

from spotify.client import BaseClient
from spotify.exceptions import ArtistError
from spotify.http.request import TLSClient
from spotify.login import Login
from spotify.client import BaseClient


class Artist(BaseClient, Login):
    """
    A class that represents an artist in the Spotify catalog.
    """

    def __new__(cls, login: Optional[Login] = None) -> Artist:
        instance = super(Artist, cls).__new__(cls)
        if login:
            instance.__dict__ = login.__dict__.copy()
        return instance

    def __init__(
        self,
        login: Optional[Login] = None,
        *,
        client: Optional[TLSClient] = TLSClient("chrome_120", "", auto_retries=3),
    ) -> None:
        if login and not login.logged_in:
            raise ValueError("Must be logged in")

        self._login: bool = bool(login)
        super().__init__(client=login.client if self._login else client)

    def query_artists(
        self, query: str, /, limit: Optional[int] = 10, *, offset: Optional[int] = 0
    ) -> Mapping[str, Any]:
        """Searches for an artist in the Spotify catalog"""
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "searchArtists",
            "variables": json.dumps(
                {
                    "searchTerm": query,
                    "offset": offset,
                    "limit": limit,
                    "numberOfTopResults": 5,
                    "includeAudiobooks": True,
                    "includePreReleases": False,
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.part_hash("searchArtists"),
                    }
                }
            ),
        }

        resp = self.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise ArtistError("Could not get artists", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise ArtistError("Invalid JSON")

        return resp.response

    def paginate_artists(
        self, query: str, /
    ) -> Generator[Mapping[str, Any], None, None]:
        """
        Generator that fetches artists in chunks

        Note: If total_tracks <= 100, then there is no need to paginate
        """
        UPPER_LIMIT: int = 100

        # We need to get the total artists first
        artists = self.query_artists(query, limit=UPPER_LIMIT)
        total_count: int = artists["data"]["searchV2"]["artists"]["totalCount"]

        yield artists["data"]["searchV2"]["artists"]["items"]

        if total_count <= UPPER_LIMIT:
            return

        offset = UPPER_LIMIT
        while offset < total_count:
            yield self.query_artists(query, limit=UPPER_LIMIT, offset=offset)["data"][
                "searchV2"
            ]["artists"]["items"]
            offset += UPPER_LIMIT

    def __do_follow(
        self,
        artist_id: str,
        /,
        *,
        action: Optional[Literal["addToLibrary", "removeFromLibrary"]] = "addToLibrary",
    ) -> None:
        if not self._login:
            raise ValueError("Must be logged in")

        if "artist:" in artist_id:
            artist_id = artist_id.split("artist:")[1]

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        payload = {
            "variables": {
                "uris": [
                    f"spotify:artist:{artist_id}",
                ],
            },
            "operationName": action,
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.part_hash(action),
                },
            },
        }

        resp = self.client.post(url, json=payload, authenticate=True)
        print(resp.response)

        if resp.fail:
            raise ArtistError("Could not follow artist", error=resp.error.string)

    def follow(self, artist_id: str, /) -> None:
        """Follow an artist"""
        return self.__do_follow(artist_id)

    def unfollow(self, artist_id: str, /) -> None:
        """Unfollow an artist"""
        return self.__do_follow(artist_id, action="removeFromLibrary")
