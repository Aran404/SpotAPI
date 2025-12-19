from __future__ import annotations

import json
from typing import Any
from collections.abc import Mapping, Generator
from spotapi.types.annotations import enforce
from spotapi.exceptions import AlbumError
from spotapi.http.request import TLSClient
from spotapi.client import BaseClient

__all__ = ["PublicAlbum", "AlbumError"]


@enforce
class PublicAlbum:
    """
    Allows you to get all public information on an album.

    Parameters
    ----------
    album (str): The Spotify URI of the album.
    client (TLSClient): An instance of TLSClient to use for requests.
    """

    __slots__ = (
        "base",
        "album_id",
        "album_link",
    )

    def __init__(
        self,
        album: str,
        /,
        *,
        client: TLSClient = TLSClient("chrome_120", "", auto_retries=3),
        language: str = "en",
    ) -> None:
        self.base = BaseClient(client=client, language=language)
        self.album_id = album.split("album/")[-1] if "album" in album else album
        self.album_link = f"https://open.spotify.com/album/{self.album_id}"

    def get_album_info(self, limit: int = 25, *, offset: int = 0) -> Mapping[str, Any]:
        """Gets the public public information"""
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "getAlbum",
            "variables": json.dumps(
                {
                    "locale": "",
                    "uri": f"spotify:album:{self.album_id}",
                    "offset": offset,
                    "limit": limit,
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.base.part_hash("getAlbum"),
                    }
                }
            ),
        }

        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise AlbumError("Could not get album info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise AlbumError("Invalid JSON")

        return resp.response

    def paginate_album(self) -> Generator[Mapping[str, Any], None, None]:
        """
        Generator that fetches playlist information in chunks

        NOTE: If total_count <= 343, then there is no need to paginate.
        """
        UPPER_LIMIT: int = 343
        album = self.get_album_info(limit=UPPER_LIMIT)
        total_count: int = album["data"]["albumUnion"]["tracksV2"]["totalCount"]

        yield album["data"]["albumUnion"]["tracksV2"]["items"]

        if total_count <= UPPER_LIMIT:
            return

        offset = UPPER_LIMIT
        while offset < total_count:
            yield self.get_album_info(limit=UPPER_LIMIT, offset=offset)["data"][
                "albumUnion"
            ]["tracksV2"]["items"]
            offset += UPPER_LIMIT
