"""Typed, asynchronous access to Spotify's catalogue and existing players."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .account import Account, Private
    from .blend import Blends
    from .captcha import CaptchaChallenge, CaptchaRequired, CaptchaSolver
    from .catalogue import Catalogue
    from .client import AsyncClient
    from .history import ListeningHistory
    from .library import Library, LikedTracks
    from .lyrics import LyricsClient
    from .models.search import SearchResults
    from .notifications import Notifications
    from .operations import SearchOptions
    from .password import PasswordReset
    from .player import Player
    from .playlist import Playlist, PlaylistHandler
    from .profiles import Profiles
    from .public import Public
    from .query import close_query_clients
    from .resources import SpotifyResource
    from .session import AuthSession
    from .stats import ListeningStats
    from .status import PlayerStatus
    from .types import SpotAPIError

__author__ = "Aran404"
__license__ = "GPL 3.0"

_EXPORTS = {
    "Account": ".account",
    "AsyncClient": ".client",
    "AuthSession": ".session",
    "Blends": ".blend",
    "CaptchaChallenge": ".captcha",
    "CaptchaRequired": ".captcha",
    "CaptchaSolver": ".captcha",
    "Catalogue": ".catalogue",
    "Library": ".library",
    "LikedTracks": ".library",
    "ListeningHistory": ".history",
    "ListeningStats": ".stats",
    "LyricsClient": ".lyrics",
    "Notifications": ".notifications",
    "PasswordReset": ".password",
    "Player": ".player",
    "PlayerStatus": ".status",
    "Playlist": ".playlist",
    "PlaylistHandler": ".playlist",
    "Private": ".account",
    "Profiles": ".profiles",
    "Public": ".public",
    "SearchOptions": ".operations",
    "SearchResults": ".models.search",
    "SpotAPIError": ".types",
    "SpotifyResource": ".resources",
    "close_query_clients": ".query",
}
__all__ = (
    "Account",
    "AsyncClient",
    "AuthSession",
    "Blends",
    "CaptchaChallenge",
    "CaptchaRequired",
    "CaptchaSolver",
    "Catalogue",
    "Library",
    "LikedTracks",
    "ListeningHistory",
    "ListeningStats",
    "LyricsClient",
    "Notifications",
    "PasswordReset",
    "Player",
    "PlayerStatus",
    "Playlist",
    "PlaylistHandler",
    "Private",
    "Profiles",
    "Public",
    "SearchOptions",
    "SearchResults",
    "SpotAPIError",
    "SpotifyResource",
    "close_query_clients",
)


def __getattr__(name: str) -> Any:
    # Keep model-only imports independent of native transports and feature clients.
    module = _EXPORTS.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module, __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
