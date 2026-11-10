"""Typed, asynchronous access to Spotify's catalogue and existing players."""

from .account import Account, Private
from .blend import Blends
from .captcha import CaptchaChallenge, CaptchaRequired, CaptchaSolver
from .catalogue import Catalogue
from .client import AsyncClient
from .history import ListeningHistory
from .library import Library, LikedTracks
from .lyrics import LyricsClient
from .notifications import Notifications
from .password import PasswordReset
from .player import Player
from .playlist import Playlist, PlaylistHandler
from .profiles import Profiles
from .public import Public, SearchResults, SpotifyResource
from .query import close_query_clients
from .session import AuthSession
from .stats import ListeningStats
from .status import PlayerStatus
from .types import SpotAPIError

__author__ = "Aran404"
__license__ = "GPL 3.0"
__all__ = (
    "Account",
    "Blends",
    "CaptchaChallenge",
    "CaptchaRequired",
    "CaptchaSolver",
    "Library",
    "ListeningStats",
    "Notifications",
    "PasswordReset",
    "Playlist",
    "PlaylistHandler",
    "Private",
    "Profiles",
    "Public",
    "Player",
    "PlayerStatus",
    "LyricsClient",
    "LikedTracks",
    "ListeningHistory",
    "AuthSession",
    "Catalogue",
    "AsyncClient",
    "SearchResults",
    "SpotifyResource",
    "SpotAPIError",
    "close_query_clients",
)
