import re
import atexit
from typing import Mapping

from spotapi.exceptions import BaseClientError
from spotapi.http.request import TLSClient
from spotapi.utils.strings import parse_json_string


class BaseClient:
    """
    A base class that all the Spotify classes extend.
    This base class contains all the common methods used by the Spotify classes.

    NOTE: Should not be used directly. Use the Spotify classes instead.
    """

    def __init__(self, client: TLSClient) -> None:
        self.client = client
        self.client.authenticate = lambda kwargs: self._auth_rule(kwargs)

        self.js_pack: str | None = None
        self.client_version: str | None = None
        self.access_token: str | None = None
        self.client_token: str | None = None
        self.client_id: str | None = None
        self.device_id: str | None = None
        self.raw_hashes: str | None = None

        self.browser_version = self.client.client_identifier.split("_")[1]
        self.client.headers.update(
            {
                "Content-Type": "application/json;charset=UTF-8",
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{self.browser_version}.0.0.0 Safari/537.36",
                "Sec-Ch-Ua": f'"Chromium";v="{self.browser_version}", "Not(A:Brand";v="24", "Google Chrome";v="{self.browser_version}"',
            }
        )

        atexit.register(self.client.close)

    def _auth_rule(self, kwargs: dict) -> dict:
        if self.client_token is None:
            self.get_client_token()

        if self.access_token is None:
            self.get_session()

        if not ("headers" in kwargs):
            kwargs["headers"] = {}

        assert self.access_token is not None, "Access token is None"
        kwargs["headers"].update(
            {
                "Authorization": "Bearer " + self.access_token,
                "Client-Token": self.client_token,
                "Spotify-App-Version": self.client_version,
            }
        )

        return kwargs

    def get_session(self) -> None:
        resp = self.client.get(
            "https://open.spotify.com",
            headers={
                "User-Agent": f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{self.browser_version}.0.0.0 Safari/537.36"
            },
        )

        if resp.fail:
            raise BaseClientError("Could not get session", error=resp.error.string)

        pattern = r"https:\/\/open\.spotifycdn\.com\/cdn\/build\/web-player\/web-player.*?\.js"
        self.js_pack = re.findall(pattern, resp.response)[1]
        self.access_token = parse_json_string(resp.response, "accessToken")
        self.client_id = parse_json_string(resp.response, "clientId")
        self.device_id = parse_json_string(resp.response, "correlationId")

    def get_client_token(self) -> None:
        if not (self.client_id and self.device_id):
            self.get_session()

        if not self.client_version:
            self.get_sha256_hash()

        url = "https://clienttoken.spotify.com/v1/clienttoken"
        payload = {
            "client_data": {
                "client_version": self.client_version,
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
            "Authority": "clienttoken.spotify.com",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        resp = self.client.post(url, json=payload, headers=headers)

        if resp.fail:
            raise BaseClientError("Could not get client token", error=resp.error.string)

        if resp.response.get("response_type") != "RESPONSE_GRANTED_TOKEN_RESPONSE":
            raise BaseClientError(
                "Could not get client token", error=resp.response.get("response_type")
            )

        if not isinstance(resp.response, Mapping):
            raise BaseClientError("Invalid JSON")

        self.client_token = resp.response["granted_token"]["token"]

    def part_hash(self, name: str) -> str:
        if self.raw_hashes is None:
            self.get_sha256_hash()

        if self.raw_hashes is None:
            raise ValueError("Could not get playlist hashes")

        try:
            return self.raw_hashes.split(f'"{name}","query","')[1].split('"')[0]
        except IndexError:
            return self.raw_hashes.split(f'"{name}","mutation","')[1].split('"')[0]

    def get_sha256_hash(self) -> None:
        if self.js_pack is None:
            self.get_session()

        if self.js_pack is None:
            raise ValueError("Could not get playlist hashes")

        resp = self.client.get(self.js_pack)

        if resp.fail:
            raise BaseClientError(
                "Could not get playlist hashes", error=resp.error.string
            )

        assert isinstance(resp.response, str), "Invalid HTML response"

        self.raw_hashes = resp.response
        self.client_version = resp.response.split('clientVersion:"')[1].split('"')[0]
        # Maybe it's static? Let's not take chances.
        self.xpui_route_num = resp.response.split(':"xpui-routes-search"')[0].split(
            ","
        )[-1]
        pattern = rf'{self.xpui_route_num}:"([^"]*)"'
        self.xpui_route = re.findall(pattern, resp.response)[-1]

        resp = self.client.get(
            f"https://open.spotifycdn.com/cdn/build/web-player/xpui-routes-search.{self.xpui_route}.js"
        )

        if resp.fail:
            raise BaseClientError("Could not get xpui hashes", error=resp.error.string)

        self.raw_hashes += resp.response

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(...)"
