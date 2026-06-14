from __future__ import annotations

import hashlib
import hmac
import re
import struct
import time
from typing import NoReturn, Any

__all__: tuple[str, ...] = ("generate_totp",)

# fallback omitted for legal hygiene, extract fresh from JS bundles
FALLBACK = ...
_SECRET_RE = re.compile(
    r'secret\s*:\s*(["\'])(.*?)\1\s*,?\s*version\s*:\s*(\d+)',
    re.DOTALL,
)


def extract_totp_secret(js_bundles: dict[str, str]) -> tuple[str, int] | NoReturn:
    web_player = next(
        (src for url, src in js_bundles.items() if "/web-player." in url),
        "",
    )

    results: list[dict[str, Any]] = [
        {"secret": secret, "version": int(version)}
        for _, secret, version in _SECRET_RE.findall(web_player)
    ]

    if not results:
        raise RuntimeError(
            "No results found, fallback can be manually written if issue persists"
        )
        return FALLBACK

    latest = max(results, key=lambda d: d["version"])
    return latest["secret"], latest["version"]


def decode_secret(secret: str) -> bytes:
    xored = [ord(c) ^ (i % 33 + 9) for i, c in enumerate(secret)]
    hex_str = "".join(str(n) for n in xored).encode().hex()
    return bytes.fromhex(hex_str)


def generate_totp(
    secret_bytes: bytes,
    *,
    timestamp: float | None = None,
    step: int = 30,
    digits: int = 6,
) -> str:
    ts = timestamp if timestamp is not None else time.time()
    counter = int(ts) // step
    msg = struct.pack(">Q", counter)
    digest = hmac.new(secret_bytes, msg, hashlib.sha1).digest()

    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def build_totp(js_bundles: dict[str, str]) -> tuple[int, str]:
    secret, version = extract_totp_secret(js_bundles)
    return version, generate_totp(decode_secret(secret))
