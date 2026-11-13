"""Authenticated podcast read-along transcripts."""

from ._parsing import mapping
from ._protocol.routes import TRANSCRIPT
from .client import AsyncClient
from .models.transcripts import Transcript
from .resources import parse_spotify_resource
from .session import AuthSession


class Transcripts:
    """Read episode captions with a borrowed authenticated client.

    The caller owns the client. Availability depends on the episode, account
    and Spotify region; unavailable transcripts raise the normal HTTPError.
    No audio is downloaded or sent to a transcription service.
    """

    __slots__ = ("http",)

    def __init__(self, client: AsyncClient | AuthSession) -> None:
        self.http = client if isinstance(client, AsyncClient) else client.client

    async def get(self, episode: str) -> Transcript:
        """Read timed captions for an episode ID, URI or share URL.

        Requires an authenticated session. Missing/malformed envelopes raise
        BaseClientError; authentication and availability errors remain HTTPError.
        """
        resource = parse_spotify_resource(episode, "episode")
        response = await self.http.get(
            TRANSCRIPT.url(episode=resource.id),
            authorized=True,
            headers={"accept": "application/json"},
            query={"format": "json"},
        )
        return Transcript.from_dict(mapping(response.json))
