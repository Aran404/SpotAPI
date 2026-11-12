"""Create shareable Blend invitations and join an invitation explicitly."""

from __future__ import annotations

from ._parsing import mapping
from ._protocol.routes import BLEND_CREATE, BLEND_JOIN
from .client import AsyncClient
from .models.blend import BlendInvitation
from .resources import SpotifyResource, parse_spotify_resource
from .session import AuthSession
from .types import BaseClientError


class Blends:
    """Create and join Blend invitations with a borrowed authenticated client.

    Both operations change server state and make one attempt. Sharing the
    returned invitation URL remains the caller's responsibility.
    """

    __slots__ = (
        "http",
        "session",
    )

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        """Borrow the caller's authenticated Spotify session."""
        self.session = client.session if isinstance(client, AsyncClient) else client
        self.http = self.session.client

    async def create(self) -> BlendInvitation:
        """Create a shareable invitation for the current account.

        Returns:
            The invitation ID and its normalized sharing URL.

        A failed response can follow a successful server-side change. The request
        is never automatically replayed.
        """
        response = await self.http.post(
            BLEND_CREATE,
            authorized=True,
            query={"market": "from_token"},
            max_attempts=1,
        )
        invitation = mapping(response.json).get("invite")
        if not isinstance(invitation, str):
            raise BaseClientError("Spotify returned no Blend invitation")
        return BlendInvitation.parse(invitation)

    async def join(self, invitation: str | BlendInvitation) -> SpotifyResource:
        """Join an invitation and return the resulting playlist identity.

        Args:
            invitation: A Blend invitation URL, ID or parsed invitation model.

        This changes the current account's Blend membership. It is sent once;
        check current membership before retrying an ambiguous failure.
        """
        invite = BlendInvitation.parse(invitation) if isinstance(invitation, str) else invitation
        response = await self.http.put(
            BLEND_JOIN.url(invitation=invite.id),
            authorized=True,
            query={"market": "from_token"},
            max_attempts=1,
        )
        uri = mapping(response.json).get("playlist_uri")
        if not isinstance(uri, str):
            raise BaseClientError("Spotify returned no Blend playlist")
        return parse_spotify_resource(uri, "playlist")
