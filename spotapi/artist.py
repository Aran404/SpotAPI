from __future__ import annotations

import json
from spotapi.types.annotations import enforce
from typing import Any, Literal
from collections.abc import Mapping, Generator
from spotapi.client import BaseClient
from spotapi.exceptions import ArtistError
from spotapi.http.request import TLSClient
from spotapi.login import Login
from spotapi.client import BaseClient

__all__ = ["Artist", "ArtistError"]


@enforce
class Artist:
    """
    A class that represents an artist in the Spotify catalog.

    Parameters
    ----------
    login : Optional[Login], optional
        A logged in Login object. This is required for certain methods.
        If not provided, some methods will raise a ValueError.
    client : TLSClient, optional
        A TLSClient used for making requests to the API.
        If not provided, a default one will be used.
    """

    __slots__ = (
        "_login",
        "base",
    )

    def __init__(
        self,
        login: Login | None = None,
        *,
        client: TLSClient = TLSClient("chrome120", "", auto_retries=3),
        language: str = "en",
    ) -> None:
        if login and not login.logged_in:
            raise ValueError("Must be logged in")

        self._login: bool = bool(login)
        self.base = BaseClient(client=login.client if (login is not None) else client, language=language)

    def query_artists(
        self, query: str, /, limit: int = 10, *, offset: int = 0
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
                        "sha256Hash": self.base.part_hash("searchArtists"),
                    }
                }
            ),
        }

        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise ArtistError("Could not get artists", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise ArtistError("Invalid JSON")

        return resp.response

    def get_artist(
        self, artist_id: str, /, *, locale_code: str = "en"
    ) -> Mapping[str, Any]:
        """Gets an artist by ID"""
        if "artist:" in artist_id:
            artist_id = artist_id.split("artist:")[-1]

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "queryArtistOverview",
            "variables": json.dumps(
                {
                    "uri": f"spotify:artist:{artist_id}",
                    "locale": locale_code,
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.base.part_hash("queryArtistOverview"),
                    }
                }
            ),
        }

        resp = self.base.client.get(url, params=params, authenticate=True)

        if resp.fail:
            raise ArtistError("Could not get artist by ID", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise ArtistError("Invalid JSON response")

        return resp.response

    def paginate_artists(
        self, query: str, /
    ) -> Generator[Mapping[str, Any], None, None]:
        """
        Generator that fetches artists in chunks

        Note: If total_count <= 100, then there is no need to paginate
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

    def get_artist_discography(
        self,
        artist_id: str,
        /,
        *,
        section: Literal["all", "albums", "singles", "compilations"] = "all",
        offset: int = 0,
        limit: int = 50,
        order: Literal["DATE_DESC", "DATE_ASC"] = "DATE_DESC",
    ) -> Mapping[str, Any]:
        """Gets an artist's discography with pagination.

        Unlike queryArtistOverview (capped per section), the discography operations
        support proper offset/limit/order. Section 'all' merges albums + singles +
        compilations sorted by date.
        """
        if "artist:" in artist_id:
            artist_id = artist_id.split("artist:")[-1]

        operation_name = {
            "all": "queryArtistDiscographyAll",
            "albums": "queryArtistDiscographyAlbums",
            "singles": "queryArtistDiscographySingles",
            "compilations": "queryArtistDiscographyCompilations",
        }[section]
        url = "https://api-partner.spotify.com/pathfinder/v2/query"
        payload = {
            "variables": {
                "uri": f"spotify:artist:{artist_id}",
                "offset": offset,
                "limit": limit,
                "order": order,
            },
            "operationName": operation_name,
            "extensions": {
                "persistedQuery": {
                    "version": 1,
                    "sha256Hash": self.base.part_hash(operation_name),
                },
            },
        }

        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise ArtistError(
                "Could not get artist discography", error=resp.error.string
            )

        if not isinstance(resp.response, Mapping):
            raise ArtistError("Invalid JSON response")

        return resp.response

    def paginate_artist_discography(
        self,
        artist_id: str,
        /,
        *,
        section: Literal["all", "albums", "singles", "compilations"] = "all",
        order: Literal["DATE_DESC", "DATE_ASC"] = "DATE_DESC",
    ) -> Generator[Mapping[str, Any], None, None]:
        """Generator that fetches an artist's discography in chunks.

        Note: If total_count <= 50, then there is no need to paginate.
        """
        UPPER_LIMIT: int = 50

        first = self.get_artist_discography(
            artist_id, section=section, offset=0, limit=UPPER_LIMIT, order=order
        )
        section_data = (
            first.get("data", {})
            .get("artistUnion", {})
            .get("discography", {})
            .get(section, {})
        )
        items = section_data.get("items") or []
        total_count: int = section_data.get("totalCount") or len(items)

        yield items

        if total_count <= UPPER_LIMIT:
            return

        offset = UPPER_LIMIT
        while offset < total_count:
            resp = self.get_artist_discography(
                artist_id,
                section=section,
                offset=offset,
                limit=UPPER_LIMIT,
                order=order,
            )
            page_items = (
                resp.get("data", {})
                .get("artistUnion", {})
                .get("discography", {})
                .get(section, {})
                .get("items")
            ) or []
            if not page_items:
                break
            yield page_items
            offset += UPPER_LIMIT

    def _do_follow(
        self,
        artist_id: str,
        /,
        *,
        action: Literal["addToLibrary", "removeFromLibrary"] = "addToLibrary",
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
                    "sha256Hash": self.base.part_hash(str(action)),
                },
            },
        }

        resp = self.base.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise ArtistError("Could not follow artist", error=resp.error.string)

    def follow(self, artist_id: str, /) -> None:
        """Follow an artist"""
        return self._do_follow(artist_id)

    def unfollow(self, artist_id: str, /) -> None:
        """Unfollow an artist"""
        return self._do_follow(artist_id, action="removeFromLibrary")
