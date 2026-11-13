"""Typed, asynchronous access to Spotify's catalogue and existing players."""

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ._decoding import from_dict
    from .account import Account, Private
    from .batch import BatchItem, fetch_many
    from .blend import Blends
    from .cache import ResponseCache
    from .captcha import CaptchaChallenge, CaptchaRequired, CaptchaSolver
    from .catalogue import Catalogue
    from .charts import list_charts
    from .client import AsyncClient
    from .embeds import get_embed
    from .history import ListeningHistory
    from .library import Library, LikedTracks
    from .login import SavedSession, browser_login
    from .lyrics import LyricsClient
    from .media import Media
    from .models.embeds import Embed
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
    from .serialization import to_dict
    from .session import AuthSession
    from .stats import ListeningStats
    from .status import PlayerStatus
    from .sync import SyncCatalogue
    from .transcripts import Transcripts
    from .types import SpotAPIError

__author__ = "Aran404"
__license__ = "GPL 3.0"

_EXPORTS = {
    "from_dict": "._decoding",
    "SavedSession": ".login",
    "browser_login": ".login",
    "SyncCatalogue": ".sync",
    "ResponseCache": ".cache",
    "Media": ".media",
    "Embed": ".models.embeds",
    "get_embed": ".embeds",
    "to_dict": ".serialization",
    "BatchItem": ".models.batch",
    "fetch_many": ".batch",
    "list_charts": ".charts",
    "Transcripts": ".transcripts",
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
    "BatchItem",
    "Blends",
    "CaptchaChallenge",
    "CaptchaRequired",
    "CaptchaSolver",
    "Catalogue",
    "Embed",
    "Library",
    "LikedTracks",
    "ListeningHistory",
    "ListeningStats",
    "LyricsClient",
    "Media",
    "Notifications",
    "PasswordReset",
    "Player",
    "PlayerStatus",
    "Playlist",
    "PlaylistHandler",
    "Private",
    "Profiles",
    "Public",
    "ResponseCache",
    "SavedSession",
    "SearchOptions",
    "SearchResults",
    "SpotAPIError",
    "SpotifyResource",
    "SyncCatalogue",
    "Transcripts",
    "browser_login",
    "close_query_clients",
    "fetch_many",
    "from_dict",
    "get_embed",
    "list_charts",
    "to_dict",
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
