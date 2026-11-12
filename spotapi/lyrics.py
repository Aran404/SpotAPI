"""Premium lyrics obtained with the caller's authorized Spotify session."""

from __future__ import annotations

from urllib.parse import urlsplit

from ._parsing import mapping
from ._protocol.routes import LYRICS, LYRICS_IMAGE
from .client import AsyncClient
from .connect import ConnectEndpoints
from .models.lyrics import Lyrics
from .resources import parse_spotify_resource
from .session import AuthSession


class LyricsClient:
    """Read entitled lyrics using a borrowed authenticated client.

    The caller owns the client and its lifetime. Lyrics are fetched on demand;
    this helper neither observes playback nor starts background tasks.
    """

    __slots__ = (
        "http",
        "session",
        "_endpoints",
    )

    def __init__(self, session: AuthSession | AsyncClient) -> None:
        """Borrow an authenticated client; resolve lyrics hosts lazily."""
        self.session = session.session if isinstance(session, AsyncClient) else session
        self.http = self.session.client
        self._endpoints: ConnectEndpoints | None = None

    async def get(self, track: str, *, image_url: str | None = None) -> Lyrics:
        """Fetch the available lyrics for one track.

        Args:
            track: Spotify track ID, URI or share URL.
            image_url: Optional HTTPS cover URL used by Spotify's image-aware route.

        Returns:
            Text, provider metadata and any available line or syllable timings.

        Raises:
            ValueError: The resource or supplied image URL is invalid.
            HTTPError: Spotify rejects the request, including unavailable entitlement.
            BaseClientError: Spotify returns malformed or missing lyrics.

        Spotify's Premium entitlement is required. Unavailable lyrics are not
        represented as an empty successful result.
        """
        resource = parse_spotify_resource(track, "track")

        if image_url is not None and urlsplit(image_url).scheme != "https":
            raise ValueError("image_url must be an HTTPS image URL")

        if self._endpoints is None:
            self._endpoints = await ConnectEndpoints.resolve(self.session)

        endpoint = (
            LYRICS.url(base=self._endpoints.spclient, track=resource.id)
            if image_url is None
            else LYRICS_IMAGE.url(
                base=self._endpoints.spclient, track=resource.id, image=image_url
            )
        )
        response = await self.http.get(
            endpoint,
            authorized=True,
            headers={"accept": "application/json"},
            query={"format": "json", "vocalRemoval": "false", "market": "from_token"},
        )

        return Lyrics.from_dict(mapping(response.json))
