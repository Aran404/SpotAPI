import re
from typing import Mapping
from spotify.http.request import TLSClient
from spotify.exceptions import BaseClientError
from spotify.utils.strings import parse_json_string


class BaseClient:
    def __init__(self, *, client: TLSClient) -> None:
        self.client = client
        self.client.authenticate = lambda kwargs: self._auth_rule(kwargs)

        self.js_pack: str = None
        self.client_version: str = None
        self.access_token: str = None
        self.client_token: str = None
        self.client_id: str = None
        self.device_id: str = None
        self.raw_hashes: str = None

        self.client.headers.update(
            {
                "content-type": "application/json;charset=UTF-8",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "sec-ch-ua": '"Chromium";v="120", "Not(A:Brand";v="24", "Google Chrome";v="120"',
            }
        )

    def _auth_rule(self, kwargs: dict) -> dict:
        if not self.client_token:
            self.get_client_token()

        if not self.access_token:
            self.get_session()

        if not ("headers" in kwargs):
            kwargs["headers"] = {}

        kwargs["headers"].update(
            {
                "authorization": "Bearer " + self.access_token,
                "client-token": self.client_token,
                "spotify-app-version": self.client_version,
            }
        )

        return kwargs

    def get_session(self) -> None:
        resp = self.client.get(
            "https://open.spotify.com",
            headers={
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
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
            "authority": "clienttoken.spotify.com",
            "content-type": "application/json",
            "accept": "application/json",
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
        if not self.raw_hashes:
            self.get_sha256_hash()

        try:
            return self.raw_hashes.split(f'"{name}","query","')[1].split('"')[0]
        except IndexError:
            return self.raw_hashes.split(f'"{name}","mutation","')[1].split('"')[0]

    def get_sha256_hash(self) -> None:
        if not self.js_pack:
            self.get_session()

        resp = self.client.get(self.js_pack)

        if resp.fail:
            raise BaseClientError(
                "Could not get playlist hash", error=resp.error.string
            )

        self.raw_hashes = resp.response
        self.client_version = resp.response.split('clientVersion:"')[1].split('"')[0]
        # Maybe it's static? Let's not take chances.
        self.xpui_route_num = resp.response.split(':"xpui-routes-search"')[0].split(",")[-1]
        print(self.xpui_route_num)
        pattern = fr'{self.xpui_route_num}:"([^"]*)"' 
        self.xpui_route = re.findall(pattern, resp.response)[-1]
        print(self.xpui_route)