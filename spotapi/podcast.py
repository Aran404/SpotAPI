from __future__ import annotations

import json
from typing import Any
from collections.abc import Mapping, Generator
from spotapi.types.annotations import enforce
from spotapi.exceptions import PodcastError
from spotapi.http.request import TLSClient
from spotapi.client import BaseClient

__all__ = ["Podcast", "PodcastError"]


@enforce
class Podcast:
    """
    Allows you to get all public information on an podcast.

    Parameters
    ----------
    podcast (Optional[str]): The Spotify URI of the podcast.
    client (TLSClient): An instance of TLSClient to use for requests.
    """

    __slots__ = (
        "base",
        "podcast_link",
        "podcast_id",
    )

    def __init__(
        self,
        podcast: str | None = None,
        *,
        client: TLSClient = TLSClient("chrome_120", "", auto_retries=3),
    ) -> None:
        self.base = BaseClient(client=client)
        if podcast:
            self.podcast_id = (
                podcast.split("show/")[-1] if "show" in podcast else podcast
            )
            self.podcast_link = f"https://open.spotify.com/show/{self.podcast_id}"

    def get_episode(self, episode_id: str) -> Mapping[str, Any]:
        """Gets the information of an episode"""
        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "getEpisodeOrChapter",
            "variables": json.dumps(
                {
                    "uri": f"spotify:episode:{episode_id}",
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.base.part_hash("getEpisodeOrChapter"),
                    }
                }
            ),
        }

        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise PodcastError("Could not get episode info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise PodcastError("Invalid JSON")

        return resp.response

    def get_podcast_info(
        self, limit: int = 25, *, offset: int = 0
    ) -> Mapping[str, Any]:
        """Gets the public podcast information"""
        if not hasattr(self, "podcast_id"):
            raise PodcastError("Podcast ID must be set")

        url = "https://api-partner.spotify.com/pathfinder/v1/query"
        params = {
            "operationName": "queryPodcastEpisodes",
            "variables": json.dumps(
                {
                    "uri": f"spotify:show:{self.podcast_id}",
                    "offset": offset,
                    "limit": limit,
                }
            ),
            "extensions": json.dumps(
                {
                    "persistedQuery": {
                        "version": 1,
                        "sha256Hash": self.base.part_hash("queryPodcastEpisodes"),
                    }
                }
            ),
        }

        resp = self.base.client.post(url, params=params, authenticate=True)

        if resp.fail:
            raise PodcastError("Could not get podcast info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise PodcastError("Invalid JSON")

        return resp.response

    def paginate_podcast(self) -> Generator[Mapping[str, Any], None, None]:
        """
        Generator that fetches podcast information in chunks

        NOTE: If total_count <= 343, then there is no need to paginate.
        """
        UPPER_LIMIT: int = 343
        # We need to get the total podcasts first
        podcast = self.get_podcast_info(limit=UPPER_LIMIT)
        total_count: int = podcast["data"]["podcastUnionV2"]["episodesV2"]["totalCount"]

        yield podcast["data"]["podcastUnionV2"]["episodesV2"]["items"]

        if total_count <= UPPER_LIMIT:
            return

        offset = UPPER_LIMIT
        while offset < total_count:
            yield self.get_podcast_info(limit=UPPER_LIMIT, offset=offset)["data"][
                "podcastUnionV2"
            ]["episodesV2"]["items"]
            offset += UPPER_LIMIT
