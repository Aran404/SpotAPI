import time
import json
import base64
import pyotp
import atexit
import requests
from typing import Tuple, Literal
from collections.abc import Mapping
from spotapi.utils.logger import Logger
from spotapi.utils.logger import Logger
from spotapi.types.annotations import enforce
from spotapi.types.alias import _UStr, _Undefined
from spotapi.exceptions import BaseClientError
from spotapi.http.request import TLSClient
from spotapi.utils.strings import extract_js_links, extract_mappings, combine_chunks

# Default recaptcha site key, will update on startup if necessary
RECAPTCHA_SITE_KEY: str = "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39"
# Fallback hardcoded secret (version 18)
_FALLBACK_SECRET: Tuple[Literal[18], bytearray] = (
    18,
    bytearray(
        [70, 60, 33, 57, 92, 120, 90, 33, 32, 62, 62, 55, 126, 93, 66, 35, 108, 68]
    ),
)

# Cache storage for TOTP
_secret_cache: Tuple[int, bytearray] | None = None
_cache_expiry: float = -1
_CACHE_TTL = 15 * 60

__all__ = ["BaseClient", "BaseClientError"]


def get_latest_totp_secret() -> Tuple[int, bytearray]:
    global _secret_cache, _cache_expiry

    if _secret_cache and time.time() < _cache_expiry:
        return _secret_cache

    try:
        url = "https://github.com/Thereallo1026/spotify-secrets/blob/main/secrets/secretDict.json?raw=true"
        response = requests.get(url, timeout=5)
        if not response.ok:
            raise BaseClientError(f"Failed to fetch secrets: {response.status_code}")

        secrets = response.json()
        version = max(secrets, key=int)
        secret_list = secrets[version]

        if not isinstance(secret_list, list):
            raise BaseClientError(
                f"Expected a list of integers, got {type(secret_list)}"
            )

        _secret_cache = (version, bytearray(secret_list))
        _cache_expiry = time.time() + _CACHE_TTL
        return _secret_cache
    except Exception as e:
        Logger.error(f"Failed to fetch secrets: {e}. Falling back to default secret.")
        return _FALLBACK_SECRET


def generate_totp() -> Tuple[str, int]:
    version, secret_bytes = get_latest_totp_secret()
    transformed = [e ^ ((t % 33) + 9) for t, e in enumerate(secret_bytes)]
    joined = "".join(str(num) for num in transformed)
    hex_str = joined.encode().hex()
    secret = base64.b32encode(bytes.fromhex(hex_str)).decode().rstrip("=")
    totp = pyotp.TOTP(secret).now()
    return totp, version


@enforce
class BaseClient:
    # There are many Javasript packs, but this one contains all the "xpui" packs which contain further packs that contain the hashes we need
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
                "totpVer": version,
                "totpServer": totp,
            }
            resp = self.client.get("https://open.spotify.com/api/token", params=query)

            if resp.fail:
                raise BaseClientError(
                    "Could not get session auth tokens", error=resp.error.string
                )

            self.access_token = resp.response["accessToken"]
            self.client_id = resp.response["clientId"]

    def get_session(self) -> None:
        resp = self.client.get("https://open.spotify.com")
        if resp.fail:
            raise BaseClientError("Could not get session", error=resp.error.string)

        _all_js_packs = extract_js_links(resp.response)
        print(_all_js_packs)
        self.js_pack = next(
            (
                link
                for link in _all_js_packs
                if "web-player/web-player" in link and link.endswith(".js")
            ),
            "",
        )

        self._raw_app_server_config = resp.response.split(
            '<script id="appServerConfig" type="text/plain">'
        )[1].split("</script>")[0]
        self.server_cfg = json.loads(
            base64.b64decode(self._raw_app_server_config).decode("utf-8")
        )

        _recaptcha_key = self.server_cfg["recaptchaWebPlayerFraudSiteKey"]
        if _recaptcha_key:
            global RECAPTCHA_SITE_KEY
            RECAPTCHA_SITE_KEY = _recaptcha_key

        self.client_version = self.server_cfg["clientVersion"]
        self.device_id = self.client.cookies.get("sp_t") or ""
        self._get_auth_vars()

    def get_client_token(self) -> None:
        if not (self.client_id and self.device_id and self.client_version):
            self.get_session()

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
            raise BaseClientError(
                "Could not get general hashes", error=resp.error.string
            )

        self.raw_hashes = resp.response

        str_mapping, hash_mapping = extract_mappings(str(self.raw_hashes))
        urls = map(
            lambda s: f"https://open.spotifycdn.com/cdn/build/web-player/{s}",
            combine_chunks(str_mapping, hash_mapping),
        )

        for url in urls:
            resp = self.client.get(url)
            if resp.fail:
                raise BaseClientError(
                    "Could not get general hashes", error=resp.error.string
                )

            self.raw_hashes += resp.response

    def __str__(self) -> str:
        return f"{self.__class__.__name__}(...)"
