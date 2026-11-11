"""Create shareable Blend invitations and join an invitation explicitly."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, urlsplit

from .catalogue import SpotifyResource, parse_spotify_resource
from .client import AsyncClient
from .playback import mapping
from .session import AuthSession
from .types import BaseClientError


@dataclass(frozen=True, slots=True)
class BlendInvitation:
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


class Blends:
    """Create an invitation, then share its URL yourself."""

    __slots__ = ("session",)

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow the caller's authenticated Spotify session."""
        self.session = client.session if isinstance(client, AsyncClient) else client

    async def create(self) -> BlendInvitation:
        """Generate a new Blend invitation; this creates a shareable invitation."""
        response = await self.session.client.post(
            "https://spclient.wg.spotify.com/blend-invitation/v1/generate",
            headers=self.session.authorized_headers,
            query={"market": "from_token"},
            max_attempts=1,
        )
        invitation = mapping(response.json).get("invite")
        if not isinstance(invitation, str):
            raise BaseClientError("Spotify returned no Blend invitation")
        return BlendInvitation.parse(invitation)

    async def join(self, invitation: str | BlendInvitation) -> SpotifyResource:
        """Join a Blend invitation and return the resulting playlist resource."""
        invite = BlendInvitation.parse(invitation) if isinstance(invitation, str) else invitation
        response = await self.session.client.put(
            "https://spclient.wg.spotify.com/blend-invitation/v2/join/"
            + quote(invite.id, safe=""),
            headers=self.session.authorized_headers,
            query={"market": "from_token"},
            max_attempts=1,
        )
        uri = mapping(response.json).get("playlist_uri")
        if not isinstance(uri, str):
            raise BaseClientError("Spotify returned no Blend playlist")
        return parse_spotify_resource(uri, "playlist")
