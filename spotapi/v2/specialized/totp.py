"""TOTP helpers for Spotify's web-player authorization."""

from __future__ import annotations

import hashlib
import hmac
import re
import struct
import time

__all__ = ("generate_totp",)

_SECRET_RE = re.compile(
    r'secret\s*:\s*(["\'])(.*?)\1\s*,?\s*version\s*:\s*(\d+)',
    re.DOTALL,
)


def extract_totp_secret(js_bundles: dict[str, str]) -> tuple[str, int]:
    """Find the newest TOTP secret/version in the web-player bundle.

    Raises:
        RuntimeError: If the bundle does not contain a discoverable secret.
    """
    web_player = next(
        (source for url, source in js_bundles.items() if "/web-player." in url),
        "",
    )
    secrets = [(secret, int(version)) for _, secret, version in _SECRET_RE.findall(web_player)]

    if not secrets:
        raise RuntimeError("Could not find a TOTP secret in the web-player bundle")

    return max(secrets, key=lambda entry: entry[1])


def decode_secret(secret: str) -> bytes:
    """Decode Spotify's obfuscated secret into a TOTP key."""
    return "".join(str(ord(char) ^ (index % 33 + 9)) for index, char in enumerate(secret)).encode(
        "ascii"
    )


def generate_totp(
    secret_bytes: bytes,
    *,
    timestamp: float | None = None,
    step: int = 30,
    digits: int = 6,
) -> str:
    """Generate a standard SHA-1 time-based one-time password.

    Args:
        secret_bytes: Binary TOTP key.
        timestamp: Unix timestamp, defaulting to the current time.
        step: Time window in seconds.
        digits: Number of decimal digits in the result.

    Returns:
        Zero-padded one-time password.

    Raises:
        ValueError: If ``step`` or ``digits`` is not positive.
    """
    if step <= 0 or digits <= 0:
        raise ValueError("step and digits must be positive")

    now = time.time() if timestamp is None else timestamp
    counter = int(now) // step
    digest = hmac.new(secret_bytes, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF

    return str(code % 10**digits).zfill(digits)


def build_totp(js_bundles: dict[str, str]) -> tuple[int, str]:
    """Return the detected Spotify TOTP version and current code."""
    secret, version = extract_totp_secret(js_bundles)

    return version, generate_totp(decode_secret(secret))
