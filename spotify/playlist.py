from spotify.exceptions import PlaylistError
from spotify.http.request import TLSClient
from spotify.utils.strings import parse_json_string
from typing import Mapping, Any, Optional
from urllib.parse import urlencode
import re


class PublicPlaylist:
    def __init__(
        self,
        playlist: str,
        client: Optional[TLSClient] = TLSClient("chrome_120", "", auto_retries=3),
    ) -> None:
        self.playlist_id = (
            playlist.split("playlist/")[-1] if "playlist" in playlist else playlist
        )
        self.playlist_link = f"https://open.spotify.com/playlist/{self.playlist_id}"
        self.client = client

        self.js_pack: str = None
        self.sha256_hash: str = None
        self.access_token: str = None
        self.client_token: str = None
        self.client_id: str = None
        self.device_id: str = None

    def __get_playlist(self) -> None:
        resp = self.client.get(
            self.playlist_link,
            headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            },
        )

        if resp.fail:
            raise PlaylistError("Could not get playlist", error=resp.error.error_string)

        pattern = r"https:\/\/open\.spotifycdn\.com\/cdn\/build\/web-player\/web-player.*?\.js"
        self.js_pack = re.findall(pattern, resp.response)[1]
        self.access_token = parse_json_string(resp.response, "accessToken")
        self.client_id = parse_json_string(resp.response, "clientId")
        self.device_id = parse_json_string(resp.response, "correlationId")

    def __get_client_token(self) -> None:
        url = "https://clienttoken.spotify.com/v1/clienttoken"
        payload = {
            "client_data": {
                "client_version": "1.2.42.107.gb271b33a",
                "client_id": self.client_id,
                "js_sdk_data": {
                    "device_brand": "unknown",
                    "device_model": "unknown",
                    "os": "windows",
                    "os_version": "NT 10.0",
                    "device_id": self.device_id,
                    "device_type": "computer",
                },
            }
        }
        headers = {
            "authority": "clienttoken.spotify.com",
            "accept": "application/json",
            "accept-language": "en-US",
            "content-type": "application/json",
            "origin": "https://open.spotify.com",
            "referer": "https://open.spotify.com/",
            "sec-ch-ua": '"Chromium";v="120", "Not(A:Brand";v="24", "Google Chrome";v="120"',
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

        resp = self.client.post(url, json=payload, headers=headers)

        if resp.fail:
            raise PlaylistError(
                "Could not get client token", error=resp.error.error_string
            )

        if resp.response.get("response_type") != "RESPONSE_GRANTED_TOKEN_RESPONSE":
            raise PlaylistError(
                "Could not get client token", error=resp.response.get("response_type")
            )

        if not isinstance(resp.response, Mapping):
            raise PlaylistError("Invalid JSON")

        self.client_id = resp.response["granted_token"]["token"]

    def __get_sha256_hash(self) -> None:
        if not self.js_pack:
            self.__get_playlist()

        resp = self.client.get(self.js_pack)

        if resp.fail:
            raise PlaylistError(
                "Could not get playlist hash", error=resp.error.error_string
            )

        self.sha256_hash = resp.response.split('"fetchPlaylist","query","')[1].split(
            '"'
        )[0]

    def get_playlist_info(self, limit: Optional[int] = 25) -> Mapping[str, Any]:
        if not self.sha256_hash:
            self.__get_sha256_hash()

        if not self.client_token:
            self.__get_client_token()

        url = f"https://api-partner.spotify.com/pathfinder/v1/query"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Token": self.client_token,
        }
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Client-Token": self.client_token,
            "content-type": "application/json;charset=UTF-8",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        params = {
            "operationName": "fetchPlaylist",
            "variables": '{"uri":"spotify:playlist:'
            + self.playlist_id
            + '","offset":0,"limit":'
            + str(limit)
            + "}",
            "extensions": '{"persistedQuery":{"version":1,"sha256Hash":"'
            + self.sha256_hash
            + '"}}',
        }

        resp = self.client.post(url, headers=headers, params=params)

        if resp.fail:
            raise PlaylistError(
                "Could not get playlist info", error=resp.error.error_string
            )

        if not isinstance(resp.response, Mapping):
            raise PlaylistError("Invalid JSON")

        return resp.response
