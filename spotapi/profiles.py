"""Public profile views, playlist pages and explicit follow operations."""

from __future__ import annotations

from collections.abc import AsyncGenerator, Sequence
from dataclasses import dataclass
from urllib.parse import quote

from .catalogue import parse_spotify_resource
from .client import AsyncClient
from .connection import Response
from .playback import integer, mapping, records
from .protobuf import ProtoMessage
from .query import QueryClient
from .session import AuthSession
from .specialized.data_wrappers import PublicProfile, from_dict
from .specialized.data_wrappers.catalogue import ProfilePlaylist
from .types import BaseClientError


def _playlist(message: ProtoMessage) -> ProfilePlaylist:
    """Decode the verified public-playlist protobuf fields."""
    return ProfilePlaylist(
        name=message.string(2),
        uri=message.string(1),
        image_url=message.string(3) or None,
        followers_count=message.integer(4),
        owner_name=message.string(5) or None,
        owner_uri=message.string(6) or None,
    )


def _profile(message: ProtoMessage) -> PublicProfile:
    """Decode a user profile and reject a missing Spotify user URI."""
    uri = message.string(1)
    if not uri.startswith("spotify:user:"):
        raise BaseClientError("Spotify returned a profile without a user URI")
    return PublicProfile(
        name=message.string(2),
        uri=uri,
        image_url=message.string(3) or None,
        followers_count=message.integer(4),
        following_count=message.integer(5),
        public_playlists=[_playlist(item) for item in message.messages(8)],
        total_public_playlists_count=message.integer(9),
    )


@dataclass(frozen=True, slots=True)
class ProfilePlaylists:
    items: tuple[ProfilePlaylist, ...]
    total: int
    offset: int
    limit: int


class Profiles:
    """Read profile views; opt into the smaller binary format with protobuf=True."""

    def __init__(self, client: AsyncClient | AuthSession, *, protobuf: bool = False) -> None:
        """Borrow a client and optionally request the verified protobuf representation."""
        self.session = client.session if isinstance(client, AsyncClient) else client
        self.queries = QueryClient(self.session)
        self.protobuf = protobuf

    async def _get(self, user: str, suffix: str = "", **query: str | int) -> Response:
        """Read a normalized public-profile endpoint with the chosen representation."""
        resource = parse_spotify_resource(user, "user")
        return await self.session.client.get(
            "https://spclient.wg.spotify.com/user-profile-view/v3/profile/"
            + quote(resource.id, safe="")
            + suffix,
            headers={
                **self.session.authorized_headers,
                "accept": "application/x-protobuf" if self.protobuf else "application/json",
            },
            query={"market": "from_token", **{key: str(value) for key, value in query.items()}},
            max_attempts=1,
        )

    async def get(self, user: str, *, playlist_limit: int = 10) -> PublicProfile:
        """Fetch a profile and its first public playlists."""
        self._limit(playlist_limit)
        response = await self._get(
            user, playlist_limit=playlist_limit, artist_limit=10, episode_limit=10
        )
        if response.body:
            return _profile(ProtoMessage.decode(response.body))
        body = mapping(response.json)
        if not body.get("uri"):
            raise BaseClientError("Spotify returned no public profile")
        return from_dict(PublicProfile, body)

    async def get_playlists(
        self, user: str, *, limit: int = 50, offset: int = 0
    ) -> ProfilePlaylists:
        """Read one bounded page of a user's public playlists."""
        self._limit(limit)
        if type(offset) is not int or offset < 0:
            raise ValueError("offset must be a non-negative integer")
        response = await self._get(user, "/playlists", limit=limit, offset=offset)
        if response.body:
            message = ProtoMessage.decode(response.body)
            items = tuple(_playlist(item) for item in message.messages(1))
            return ProfilePlaylists(items, message.integer(2), offset, limit)

        body = mapping(response.json)
        if not isinstance(body.get("public_playlists"), list):
            raise BaseClientError("Spotify returned no public playlist page")
        items = tuple(from_dict(ProfilePlaylist, row) for row in records(body["public_playlists"]))
        return ProfilePlaylists(
            items, integer(body.get("total_public_playlists_count")), offset, limit
        )

    async def playlist_pages(
        self, user: str, *, limit: int = 50
    ) -> AsyncGenerator[ProfilePlaylists, None]:
        """Stream public-playlist pages lazily until the returned total is reached."""
        offset = 0
        while True:
            page = await self.get_playlists(user, limit=limit, offset=offset)
            if not page.items:
                return
            yield page
            offset += len(page.items)
            if offset >= page.total:
                return

    async def followers(self, user: str) -> tuple[PublicProfile, ...]:
        """Read Spotify's follower preview, which is capped by the server."""
        return await self._connections(user, "followers")

    async def following(self, user: str) -> tuple[PublicProfile, ...]:
        """Read Spotify's following preview; the server caps this list at 1,000."""
        return await self._connections(user, "following")

    async def _connections(self, user: str, kind: str) -> tuple[PublicProfile, ...]:
        """Parse the server's capped follower or following preview."""
        response = await self._get(user, "/" + kind)
        if response.body:
            return tuple(_profile(item) for item in ProtoMessage.decode(response.body).messages(1))
        return tuple(
            from_dict(PublicProfile, row)
            for row in records(mapping(response.json).get("profiles"))
        )

    async def is_following(self, users: Sequence[str]) -> tuple[bool, ...]:
        """Return followed-user flags in input order, batching at most 50 users."""
        if isinstance(users, str):
            raise TypeError("Pass a collection of users")
        uris = [parse_spotify_resource(user, "user").uri for user in users]
        flags: list[bool] = []
        for offset in range(0, len(uris), 50):
            batch = uris[offset : offset + 50]
            response = await self.queries.pathfinder_query(
                {"uris": batch}, "isFollowingUsers", max_attempts=1
            )
            rows = records(response.get("users"))
            if len(rows) != len(batch) or any(
                not isinstance(row.get("following"), bool) for row in rows
            ):
                raise BaseClientError("Spotify returned an incomplete follow lookup")
            flags.extend(row["following"] for row in rows)
        return tuple(flags)

    async def follow(self, *users: str) -> None:
        """Follow the supplied users; this can notify other Spotify users."""
        await self._follow("followUsers", users)

    async def unfollow(self, *users: str) -> None:
        """Unfollow the supplied Spotify users."""
        await self._follow("unfollowUsers", users)

    async def _follow(self, operation: str, users: Sequence[str]) -> None:
        """Validate each result; partial changes may apply and are never replayed."""
        names = list(dict.fromkeys(parse_spotify_resource(user, "user").id for user in users))
        for offset in range(0, len(names), 50):
            batch = names[offset : offset + 50]
            response = await self.queries.pathfinder_query(
                {"usernames": batch}, operation, max_attempts=1
            )
            rows = records(mapping(response.get(operation)).get("responses"))
            expected = "FollowUserResult" if operation == "followUsers" else "UnfollowUserResult"
            if (
                len(rows) != len(batch)
                or any(
                    not isinstance(row.get("username"), str)
                    or row.get("__typename") != expected
                    or row.get("result") is not True
                    for row in rows
                )
                or {row["username"] for row in rows} != set(batch)
            ):
                raise BaseClientError(
                    "Spotify did not confirm every follow change; reconcile followed state before retrying"
                )

    @staticmethod
    def _limit(value: int) -> None:
        """Validate the profile endpoint's bounded page size and offset."""
        if type(value) is not int or not 1 <= value <= 200:
            raise ValueError("limit must be between 1 and 200")
