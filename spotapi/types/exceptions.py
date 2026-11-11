"""Public SpotAPI exception types."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from spotapi.connection.types import Response

__all__ = (
    "SpotAPIError",
    "HTTPError",
    "WebsocketError",
    "BaseClientError",
    "PlaylistError",
)


class SpotAPIError(Exception):
    """Base class for exceptions defined by SpotAPI."""


# Retain the previous base name for code importing it from this module.
ParentException = SpotAPIError


class HTTPError(SpotAPIError):
    """An HTTP request failed or returned an unsuccessful response."""

    def __init__(
        self, message: str, *, status_code: int | None = None, response: Response | None = None
    ) -> None:
        """Retain error context and status without embedding credential-bearing response bodies."""
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class WebsocketError(SpotAPIError):
    """A WebSocket operation failed."""


class BaseClientError(SpotAPIError):
    """A client-side request or response could not be processed."""


class PlaylistError(SpotAPIError):
    """A playlist operation failed."""
