"""Spotify endpoints and encoded resource paths used by the built-in features."""

from dataclasses import dataclass
from types import MappingProxyType
from urllib.parse import quote

SPCLIENT = "https://spclient.wg.spotify.com"
OPEN = "https://open.spotify.com"
ACCOUNTS = "https://accounts.spotify.com"
PATHFINDER = "https://api-partner.spotify.com/pathfinder/v2/query"
RESOLVE = "https://apresolve.spotify.com/"
TOKEN = f"{OPEN}/api/token"
CLIENT_TOKEN = "https://clienttoken.spotify.com/v1/clienttoken"
PLAYLIST_BASE = f"{SPCLIENT}/playlist/v2/playlist"
PLAYLIST_UPLOAD = "https://image-upload.spotify.com/v4/playlist"
BLEND_CREATE = f"{SPCLIENT}/blend-invitation/v1/generate"
NOTIFICATIONS = f"{SPCLIENT}/gander/v2/GetNotifications"
NOTIFICATIONS_UNREAD = f"{SPCLIENT}/gander/v2/GetUserHasUnreadNotification"
NOTIFICATIONS_SEEN = f"{SPCLIENT}/gander/v2/ResetLatestCursor"
RECOMMENDATIONS = f"{SPCLIENT}/playlistextender/extendp/"
CANVASES = f"{SPCLIENT}/canvaz-cache/v0/canvases"


@dataclass(frozen=True, slots=True)
class Route:
    """A path template whose resource parameters are encoded as individual segments.

    ``base`` can be replaced with a resolved regional host. Query parameters
    belong to the HTTP client's ``query`` argument, not the path template.
    ``safe`` preserves service-specific delimiters, such as radio-seed URI
    colons; slashes in resource values remain encoded.
    """

    path: str
    base: str = SPCLIENT
    safe: str = ""

    def url(self, *, base: str | None = None, **parameters: str) -> str:
        """Build a URL, encoding each supplied parameter exactly once."""
        encoded = {name: quote(value, safe=self.safe) for name, value in parameters.items()}
        return f"{(base or self.base).rstrip('/')}{self.path.format_map(encoded)}"


LYRICS = Route("/color-lyrics/v2/track/{track}")
RADIO = Route("/inspiredby-mix/v2/seed_to_playlist/{seed}", safe=":")
LYRICS_IMAGE = Route("/color-lyrics/v2/track/{track}/image/{image}")
PROFILE = Route("/user-profile-view/v3/profile/{user}")
PROFILE_SECTION = Route("/user-profile-view/v3/profile/{user}/{section}")
BLEND_JOIN = Route("/blend-invitation/v2/join/{invitation}")
PLAYLIST = Route("/playlist/v2/playlist/{playlist}")
PLAYLIST_CHANGES = Route("/playlist/v2/playlist/{playlist}/changes")
PLAYLIST_REGISTER_IMAGE = Route("/playlist/v2/playlist/{playlist}/register-image")
ROOTLIST = Route("/playlist/v2/user/{user}/rootlist/changes")
CONNECT_OBSERVER = Route("/connect-state/v1/devices/{device}")
CONNECT_ROUTES = MappingProxyType(
    {
        "player/command": Route("/connect-state/v1/player/command/from/{source}/to/{target}"),
        "connect/volume": Route("/connect-state/v1/connect/volume/from/{source}/to/{target}"),
        "connect/transfer": Route("/connect-state/v1/connect/transfer/from/{source}/to/{target}"),
    }
)
DEVICE = Route("/track-playback/v1/devices/{device}")
DEVICE_STATE = Route("/track-playback/v1/devices/{device}/state")
DEVICE_REGISTER = Route("/track-playback/v1/devices")

TRANSCRIPT = Route("/transcript-read-along/v2/episode/{episode}")
