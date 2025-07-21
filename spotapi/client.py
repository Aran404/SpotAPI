import re
import base64
import pyotp
import atexit
import requests
from typing import Tuple
from collections.abc import Mapping
from spotapi.types.annotations import enforce
from spotapi.types.alias import _UStr, _Undefined
from spotapi.exceptions import BaseClientError
from spotapi.http.request import TLSClient

__all__ = ["BaseClient", "BaseClientError"]


def get_latest_totp_secret() -> Tuple[int, bytearray]:
    url = "https://github.com/Thereallo1026/spotify-secrets/blob/main/secrets/secretDict.json?raw=true"
    response = requests.get(url)
    response.raise_for_status()
    secrets = response.json()

    version = max(secrets, key=int)
    secret_list = secrets[version]

    if not isinstance(secret_list, list):
        raise TypeError(f"Expected a list of integers, got {type(secret_list)}")

    return version, bytearray(secret_list)


def generate_totp() -> Tuple[str, int]:
    version, secret_bytes = get_latest_totp_secret()
    print(f"Using secret version: {version}: {secret_bytes}")
    transformed = [e ^ ((t % 33) + 9) for t, e in enumerate(secret_bytes)]
    joined = "".join(str(num) for num in transformed)
    hex_str = joined.encode().hex()
    secret = base64.b32encode(bytes.fromhex(hex_str)).decode().rstrip("=")
    totp = pyotp.TOTP(secret).now()
    return totp, version

@enforce
class BaseClient:
    js_pack: _UStr = _Undefined
    client_version: _UStr = _Undefined
    access_token: _UStr = _Undefined
    client_token: _UStr = _Undefined
    client_id: _UStr = _Undefined
    device_id: _UStr = _Undefined
    raw_hashes: _UStr = _Undefined

    def __init__(self, client: TLSClient) -> None:
        self.client = client
        self.client.authenticate = lambda kwargs: self._auth_rule(kwargs)

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
        if self.client_token is _Undefined:
            self.get_client_token()

        if self.access_token is _Undefined:
            self.get_session()

        if "headers" not in kwargs:
            kwargs["headers"] = {}

        kwargs["headers"].update(
            {
                "Authorization": "Bearer " + str(self.access_token),
                "Client-Token": self.client_token,
                "Spotify-App-Version": self.client_version,
            }.items()
        )

        return kwargs

    def _get_auth_vars(self) -> None:
        if self.access_token is _Undefined or self.client_id is _Undefined:
            totp, version = generate_totp()
            query = {
                "reason": "init",
                "productType": "web-player",
                "totp": totp,
                "totpVer": version,
                "totpServer": totp,
            }
            resp = self.client.get("https://open.spotify.com/api/token", params=query)

            if resp.fail:
                raise BaseClientError("Could not get session auth tokens", error=resp.error.string)

            self.access_token = resp.response["accessToken"]
            self.client_id = resp.response["clientId"]

    def get_session(self) -> None:
        resp = self.client.get("https://open.spotify.com")
        if resp.fail:
            raise BaseClientError("Could not get session", error=resp.error.string)

        try:
            pattern = r"https:\/\/open\.spotifycdn\.com\/cdn\/build\/web-player\/web-player.*?\.js"
            self.js_pack = re.findall(pattern, resp.response)[1]
        except IndexError:
            pattern = r"https:\/\/open-exp.spotifycdn\.com\/cdn\/build\/web-player\/web-player.*?\.js"
            self.js_pack = re.findall(pattern, resp.response)[1]

        self.device_id = self.client.cookies.get("sp_t") or ""
        self._get_auth_vars()

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
        if self.raw_hashes is _Undefined:
            self.get_sha256_hash()

        if self.raw_hashes is _Undefined:
            raise ValueError("Could not get playlist hashes")

        try:
            return str(self.raw_hashes).split(f'"{name}","query","')[1].split('"')[0]
        except IndexError:
            return str(self.raw_hashes).split(f'"{name}","mutation","')[1].split('"')[0]

    def get_sha256_hash(self) -> None:
        if self.js_pack is _Undefined:
            self.get_session()

        if self.js_pack is _Undefined:
            raise ValueError("Could not get playlist hashes")

        resp = self.client.get(str(self.js_pack))
        if resp.fail:
            raise BaseClientError("Could not get playlist hashes", error=resp.error.string)

        assert isinstance(resp.response, str), "Invalid HTML response"
        self.raw_hashes = resp.response
        self.client_version = resp.response.split('clientVersion:"')[1].split('"')[0]

        self.xpui_route_num = resp.response.split(':"xpui-routes-search"')[0].split(",")[-1]
        self.xpui_route_tracks_num = resp.response.split(':"xpui-routes-track-v2"')[0].split(",")[-1]

        xpui_route_pattern = rf'{self.xpui_route_num}:"([^"]*)"'
        self.xpui_route = re.findall(xpui_route_pattern, resp.response)[-1]

        xpui_route_tracks_pattern = rf'{self.xpui_route_tracks_num}:"([^"]*)"'
        self.xpui_route_tracks = re.findall(xpui_route_tracks_pattern, resp.response)[-1]

        urls = (
            f"https://open.spotifycdn.com/cdn/build/web-player/xpui-routes-search.{self.xpui_route}.js",
            f"https://open.spotifycdn.com/cdn/build/web-player/xpui-routes-track-v2.{self.xpui_route_tracks}.js",
        )

        for url in urls:
            resp = self.client.get(url)
            if resp.fail:
                raise BaseClientError("Could not get xpui hashes", error=resp.error.string)
            self.raw_hashes += resp.response

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(...)"
