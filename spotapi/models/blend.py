"""Shareable Blend invitations, independent of membership changes."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlsplit


@dataclass(frozen=True, slots=True)
class BlendInvitation:
    """A shareable Blend invitation, independent of joining it.

    ``parse`` accepts a Spotify invitation URL or invitation ID and performs
    no network request. Joining remains an explicit account operation.
    """

    id: str
    url: str

    @classmethod
    def parse(cls, value: str) -> BlendInvitation:
        """Normalize a Spotify Blend invitation URL or invitation ID."""
        if "://" in value:
            parsed = urlsplit(value)
            if parsed.scheme != "https" or parsed.hostname != "open.spotify.com":
                raise ValueError("Use a Spotify Blend invitation URL")
            parts = parsed.path.strip("/").split("/")
            if len(parts) != 3 or parts[:2] != ["blend", "taste-match"]:
                raise ValueError("This Spotify link is not a Blend invitation")
            identifier = parts[-1]
            url = value
        else:
            identifier = value
            url = "https://open.spotify.com/blend/taste-match/" + quote(identifier, safe="")

        if (
            not identifier
            or len(identifier) > 128
            or not identifier.replace("-", "").replace("_", "").isalnum()
        ):
            raise ValueError("Invalid Blend invitation ID")
        return cls(identifier, url)
