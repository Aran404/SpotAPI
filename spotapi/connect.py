"""Resolve the regional endpoints used by Spotify Connect."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlsplit

from .session import AuthSession
from .types import BaseClientError


@dataclass(frozen=True, slots=True)
class ConnectEndpoints:
    dealer: str
    spclient: str
    playback: str = "https://spclient.wg.spotify.com"

    @classmethod
    async def resolve(cls, session: AuthSession) -> ConnectEndpoints:
        """Resolve Spotify's current dealer and spclient hosts for this session."""
        response = await session.client.get(
            "https://apresolve.spotify.com/", query=[("type", "dealer-g2"), ("type", "spclient")]
        )

        body = response.json

        if body is None:
            raise BaseClientError("Spotify endpoint resolver returned no JSON")

        endpoints: list[str] = []

        for kind, scheme in (("dealer-g2", "wss"), ("spclient", "https")):
            hosts: object = body.get(kind)

            if not isinstance(hosts, list) or not hosts or not isinstance(hosts[0], str):
                raise BaseClientError(f"Spotify endpoint resolver returned no {kind} host")

            endpoint = f"{scheme}://{hosts[0]}"
            parsed = urlsplit(endpoint)

            if (
                not parsed.hostname
                or not parsed.hostname.endswith(".spotify.com")
                or parsed.port != 443
                or parsed.username
                or parsed.path
                or parsed.query
                or parsed.fragment
            ):
                raise BaseClientError("Spotify endpoint resolver returned an invalid host")

            endpoints.append(endpoint)

        return cls(*endpoints)
