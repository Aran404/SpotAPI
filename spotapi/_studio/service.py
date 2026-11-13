"""Keep the GUI thin: own sessions here and delegate each feature to SpotAPI."""

from __future__ import annotations

import asyncio
from collections import OrderedDict, deque
from collections.abc import AsyncGenerator, Mapping
from contextlib import aclosing
from dataclasses import fields, is_dataclass, replace
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, TypeVar, cast

from spotapi import (
    Account,
    AsyncClient,
    CaptchaRequired,
    Catalogue,
    LyricsClient,
    Player,
    Playlist,
    PlaylistHandler,
)
from spotapi.models import Lyrics, PlaybackTrack, PlayerState, TimeRange
from spotapi.types import HTTPError, SpotAPIError

from .actions import ACTIONS, manifest
from .lyrics import get_public_lyrics

T = TypeVar("T")
_ACTIONS = {action.id: action for action in ACTIONS}
_OPERATIONS = _ACTIONS.keys() | {
    "bootstrap",
    "search",
    "detail",
    "library",
    "liked",
    "top",
    "notifications",
    "player",
    "refresh_player",
    "recents",
    "toggle",
    "pause",
    "resume",
    "next",
    "previous",
    "restart",
    "shuffle",
    "repeat",
}


def serialize(value: object) -> Any:
    """Convert display models into JSON values without serializing session objects."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Enum):
        return serialize(value.value)
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: serialize(getattr(value, field.name))
            for field in fields(value)
            if field.name not in {"session_id", "server_nonce", "client_nonce"}
        }
    if isinstance(value, Mapping):
        return {
            str(key): serialize(item) for key, item in cast(Mapping[object, object], value).items()
        }
    if isinstance(value, (tuple, list)):
        return [serialize(item) for item in cast(list[object] | tuple[object, ...], value)]
    raise TypeError(f"No display serializer for {type(value).__name__}")


async def first_page(pages: AsyncGenerator[T, None]) -> T | None:
    """Read one bounded page and immediately release its generator resources."""
    async with aclosing(pages):
        return await anext(pages, None)


class Studio:
    """Own one catalogue, optional account and explicitly connected existing player."""

    def __init__(self) -> None:
        """Prepare bounded display state; defer network work until a request or sign-in."""
        self.catalogue = Catalogue()
        self._catalogue_started = False
        self.client: AsyncClient | None = None
        self.account: Account | None = None
        self.player: Player | None = None
        self.events: deque[dict[str, Any]] = deque(maxlen=80)
        self._queue_metadata: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lyrics_cache: OrderedDict[str, Lyrics] = OrderedDict()
        self._player_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._closed = False

    async def authenticate(self, cookie: str) -> None:
        """Validate a new session before replacing the working session; never return cookies."""
        if self._closed:
            raise RuntimeError("Studio is closed")
        client = await AsyncClient.from_cookies(cookie)
        try:
            account = Account(client)
            await account.get_profile()
            async with self._lock:
                if self._closed:
                    raise RuntimeError("Studio closed during sign-in")
                await self._disconnect()
                self.client = client
                self.account = account
                self.catalogue = Catalogue(client)
                self._catalogue_started = False
        except BaseException:
            await client.close()
            raise

    async def close(self) -> None:
        """Close the player before its borrowed authentication and native HTTP transport."""
        self._closed = True
        async with self._lock:
            await self._disconnect()

    async def _disconnect(self) -> None:
        """Release the observer, timers and authenticated client in ownership order."""
        try:
            await self._stop_player()
        finally:
            self.account = None
            self.events.clear()
            self._queue_metadata.clear()
            try:
                await self.catalogue.close()
            finally:
                self._catalogue_started = False
                client, self.client = self.client, None
                if client is not None:
                    await client.close()

    async def _connect_player(self) -> Player:
        """Attach to existing players without registering an audio renderer."""
        if self.client is None:
            raise ValueError("Sign in to connect an existing Spotify player")
        if self.player is None:
            player = Player(self.client, name="SpotAPI Studio")

            @player.listen("state_update")
            async def on_state(before: PlayerState | None, state: PlayerState) -> None:
                """Retain a small summary of a real dealer-state event."""
                self.events.append(
                    {
                        "event": "state",
                        "at": datetime.now().isoformat(),
                        "data": {"track": serialize(state.track), "paused": state.is_paused},
                    }
                )

            @player.listen("pause")
            async def on_pause(state: PlayerState) -> None:
                """Record the pause callback without retaining the entire queue."""
                self.events.append(
                    {
                        "event": "pause",
                        "at": datetime.now().isoformat(),
                        "data": {"track": serialize(state.track), "paused": state.is_paused},
                    }
                )

            @player.listen("resume")
            async def on_resume(state: PlayerState) -> None:
                """Record the resume callback without retaining the entire queue."""
                self.events.append(
                    {
                        "event": "resume",
                        "at": datetime.now().isoformat(),
                        "data": {"track": serialize(state.track), "paused": state.is_paused},
                    }
                )

            self.player = player
            self._player_task = asyncio.create_task(player.start(), name="studio-player")
            self._player_task.add_done_callback(self._player_done)

        player, runner = self.player, self._player_task
        assert player is not None and runner is not None
        if not player.is_ready:
            ready = asyncio.create_task(player.wait_until_ready())
            try:
                done, _ = await asyncio.wait(
                    {ready, runner}, timeout=15, return_when=asyncio.FIRST_COMPLETED
                )
                if runner in done:
                    await runner
                    raise RuntimeError("Player disconnected; use the refresh button to reconnect")
                if not done:
                    raise TimeoutError("Waiting for Spotify's player connection")
                await ready
            finally:
                if not ready.done():
                    ready.cancel()
                await asyncio.gather(ready, return_exceptions=True)
        return self.player

    def _player_done(self, task: asyncio.Task[None]) -> None:
        """Observe a stopped supervisor without logging account data or hiding its exception."""
        if not task.cancelled() and (error := task.exception()) is not None:
            self.events.append(
                {"event": "error", "at": datetime.now().isoformat(), "type": type(error).__name__}
            )

    async def _stop_player(self) -> None:
        """Close the player and await its supervisor before its borrowed HTTP client closes."""
        player, self.player = self.player, None
        runner, self._player_task = self._player_task, None
        try:
            if player is not None:
                await player.close()
        finally:
            if runner is not None:
                if not runner.done():
                    runner.cancel()
                await asyncio.gather(runner, return_exceptions=True)

    async def request(self, action: str, values: Mapping[str, str]) -> dict[str, Any]:
        """Run a known command and return a display result or a credential-free error."""
        try:
            if action not in _OPERATIONS:
                raise ValueError("Unknown Studio operation")
            operation = _ACTIONS.get(action)
            if operation and operation.changes and values.get("confirmed") != "true":
                raise ValueError("Confirm this action before sending it to Spotify")
            async with self._lock:
                async with asyncio.timeout(45):
                    if self._closed:
                        raise RuntimeError("Studio is closed")
                    if not self._catalogue_started:
                        await self.catalogue.__aenter__()
                        self._catalogue_started = True
                    data = await self._execute(action, values)
            if data is None:
                data = (
                    {"completed": True}
                    if operation and operation.changes
                    else {"available": False}
                )
            return {"ok": True, "data": serialize(data)}
        except CaptchaRequired as error:
            return {
                "ok": False,
                "error": "Spotify requires a fresh CAPTCHA token for this action. Supply one from your own provider.",
                "challenge": serialize(error.challenge),
            }
        except HTTPError as error:
            return {
                "ok": False,
                "error": f"Spotify refused the request (HTTP {error.status_code}). Refresh your session if authentication expired.",
            }
        except (ValueError, TypeError, RuntimeError, TimeoutError) as error:
            return {"ok": False, "error": str(error) or "The request timed out"}
        except Exception as error:
            return {
                "ok": False,
                "error": f"{type(error).__name__}: Spotify could not complete this operation",
            }

    async def _execute(self, action: str, values: Mapping[str, str]) -> object:
        """Route named features by responsibility; never invoke arbitrary client attributes."""
        if action == "lyrics":
            return await self._lyrics(values.get("uri", ""))
        operation = _ACTIONS.get(action)
        group = operation.group if operation else ""
        if group == "Catalogue" or action in {"bootstrap", "search", "detail", "profile"}:
            return await self._catalogue_action(action, values)
        account = self.account
        if account is None or self.client is None:
            raise ValueError("Sign in to use your Spotify account")
        if group in {"Account", "People"} or action in {
            "library",
            "liked",
            "top",
            "notifications",
            "notifications_unread",
        }:
            return await self._account_action(account, action, values)
        if group in {"Library", "Social"}:
            return await self._collection_action(account, action, values)
        if group == "Playlists":
            return await self._playlist_action(action, values)
        return await self._player_action(action, values)

    async def _catalogue_action(self, action: str, values: Mapping[str, str]) -> object:
        """Read public catalogue resources with the current session's visibility."""
        uri = values.get("uri", "")
        user = values.get("user", "spotify")
        if action == "bootstrap":
            profile = self.account.profile if self.account else None
            return {
                "signed_in": self.client is not None,
                "name": profile.username if profile else "Guest",
                "actions": manifest(),
            }
        if action == "search":
            return await self.catalogue.search(
                values.get("query", "Daft Punk"),
                types=(
                    "track",
                    "artist",
                    "album",
                    "playlist",
                    "podcast",
                    "episode",
                    "audiobook",
                    "user",
                    "author",
                    "genre",
                ),
                limit=12,
            )
        if action == "detail":
            return await self.catalogue.get(uri)
        if action == "profile":
            return await self.catalogue.get_profile(user)
        catalogue_calls = {
            "track": self.catalogue.get_track,
            "album": self.catalogue.get_album,
            "artist": self.catalogue.get_artist,
            "credits": self.catalogue.get_track_credits,
            "radio": self.catalogue.get_radio,
            "recommendations": self.catalogue.get_playlist_recommendations,
            "canvas": self.catalogue.get_canvas,
            "related": self.catalogue.get_related_artists,
            "artist_top": self.catalogue.get_artist_top_tracks,
            "podcast": self.catalogue.get_podcast,
            "episode": self.catalogue.get_podcast_episode,
            "audiobook": self.catalogue.get_audiobook,
        }
        if action in catalogue_calls:
            return await catalogue_calls[action](uri)
        if action == "playlist":
            return {
                "playlist": await self.catalogue.get_playlist(uri),
                "items": await first_page(self.catalogue.get_playlist_items(uri)),
            }
        if action == "releases":
            return await first_page(self.catalogue.get_artist_releases(uri))
        if action == "episodes":
            return await first_page(self.catalogue.get_podcast_episodes(uri))

        raise ValueError("Unknown catalogue operation")

    async def _account_action(
        self, account: Account, action: str, values: Mapping[str, str]
    ) -> object:
        """Read account views or send explicit profile and follower changes."""
        user = values.get("user", "spotify")
        if action == "library":
            return await account.library.get(
                limit=50, query=values.get("query", ""), offset=int(values.get("offset", "0"))
            )
        if action == "liked":
            return await account.liked_tracks.get(limit=50, offset=int(values.get("offset", "0")))
        if action == "top":
            ranges: dict[str, TimeRange] = {
                "short_term": "short_term",
                "medium_term": "medium_term",
                "long_term": "long_term",
            }
            span = ranges.get(values.get("range", "medium_term"))
            if span is None:
                raise ValueError("Choose short_term, medium_term or long_term")
            return await account.stats.get(time_range=span, limit=20)
        if action == "notifications":
            return await account.notifications.get(cursor=values.get("cursor") or None)
        if action == "notifications_unread":
            return await account.notifications.has_unread()
        if action == "account":
            return await account.get_profile()
        if action == "plan":
            return await account.get_plan()
        if action == "verify":
            return await account.verify_login()
        if action == "validate_profile":
            return await account.validate_profile(
                **{key: val for key, val in values.items() if key in {"email", "country"} and val}
            )
        if action == "edit_profile":
            return await account.edit_profile(
                email=values.get("email") or None,
                country=values.get("country") or None,
                gender=values.get("gender") or None,
                birthdate=(
                    date.fromisoformat(values["birthdate"]) if values.get("birthdate") else None
                ),
                password=values.get("password") or None,
                token=values.get("token") or None,
            )
        if action == "change_password":
            return await account.change_password(
                values["current_password"], values["new_password"]
            )
        if action == "set_password":
            return await account.set_password(values["new_password"])
        if action == "logout_everywhere":
            await account.logout_everywhere()
            await self._disconnect()
            self.catalogue = Catalogue()
            self._catalogue_started = False
            return {"signed_out": True}
        if action in {"profile_playlists", "followers", "following"}:
            return await {
                "profile_playlists": account.profiles.get_playlists,
                "followers": account.profiles.followers,
                "following": account.profiles.following,
            }[action](user)
        if action in {"is_following", "follow", "unfollow"}:
            users = _words(values["users"])
            if action == "is_following":
                return await account.profiles.is_following(users)
            return await {
                "follow": account.profiles.follow,
                "unfollow": account.profiles.unfollow,
            }[action](*users)
        raise ValueError("Unknown account operation")

    async def _collection_action(
        self, account: Account, action: str, values: Mapping[str, str]
    ) -> object:
        """Handle saves, pins, notifications and Blend invitations independently of playback."""
        uri = values.get("uri", "")
        if action.startswith("saved_"):
            return await {
                "saved_contains": account.library.contains,
                "saved_add": account.library.add,
                "saved_remove": account.library.remove,
            }[action](_words(values["uris"]))
        if action in {"pin", "unpin"}:
            return await {"pin": account.library.pin, "unpin": account.library.unpin}[action](uri)
        if action == "blend_create":
            return await account.blends.create()
        if action == "blend_join":
            return await account.blends.join(values["invitation"])
        if action == "notifications_seen":
            return await account.notifications.mark_seen(values["cursor"])
        raise ValueError("Unknown collection operation")

    async def _playlist_action(self, action: str, values: Mapping[str, str]) -> object:
        """Delegate playlist and folder changes to reusable library helpers."""
        assert self.client is not None
        handler = PlaylistHandler(self.client)
        if action == "create_playlist":
            playlist = await handler.create_playlist(values["name"])
            return {"uri": playlist.playlist_id}
        if action == "create_folder":
            return await handler.create_folder(values["name"])
        if action == "move_folder":
            return await handler.move_items_to_folder(values["folder"], *_words(values["uris"]))
        if action == "remove_library_items":
            return await handler.remove_items(*_words(values["uris"]))
        if action in {
            "add_tracks",
            "remove_tracks",
            "remove_occurrences",
            "delete_playlist",
            "edit_playlist",
            "publish_playlist",
            "unpublish_playlist",
        }:
            playlist = Playlist(self.client, values["playlist"])
            if action == "edit_playlist":
                await playlist.edit(
                    name=values.get("name") or None, description=values.get("description")
                )
                return await playlist.get(fresh=True)
            if action in {"publish_playlist", "unpublish_playlist"}:
                return await playlist.set_published(action == "publish_playlist")
            if action == "delete_playlist":
                return await playlist.delete()
            if action == "remove_occurrences":
                return await playlist.remove_occurrences(*_words(values["uids"]))
            return await {
                "add_tracks": playlist.add_tracks,
                "remove_tracks": playlist.remove_tracks,
            }[action](*_words(values["uris"]))
        raise ValueError("Unknown playlist operation")

    async def _lyrics(self, uri: str) -> Lyrics:
        """Try the public provider first and reuse matches within Studio."""
        resource = self.catalogue.parse_url(uri, kind="track")
        if cached := self._lyrics_cache.get(resource.uri):
            self._lyrics_cache.move_to_end(resource.uri)
            return cached

        track = await self.catalogue.get_track(resource.uri)
        try:
            public = await get_public_lyrics(track)
        except ValueError:
            if self.client is None:
                raise
            public = None

        if public is not None:
            self._lyrics_cache[resource.uri] = public
            if len(self._lyrics_cache) > 24:
                self._lyrics_cache.popitem(last=False)
            return public

        if self.client is not None:
            return await LyricsClient(self.client).get(resource.uri)
        raise ValueError("No public lyrics are available for this recording.")

    async def _player_action(self, action: str, values: Mapping[str, str]) -> object:
        """Read or control the selected existing player; never render audio locally."""
        assert self.client is not None
        uri = values.get("uri", "")
        if action == "refresh_player" and self.player is not None and not self.player.is_ready:
            await self._stop_player()
        player = await self._connect_player()
        if action in {"player", "refresh_player"}:
            if action == "refresh_player":
                await player.refresh()
            snapshot = serialize(player.state)
            if player.state is not None:
                snapshot["position"] = player.state.position_ms
            return {
                "state": snapshot,
                "queue": await self._queue_preview(player),
                "devices": player.devices,
                "events": list(self.events),
                "timer": player.sleep_timer_remaining,
            }
        if action == "recents":
            return await player.history.get(limit=30)
        if action == "play":
            return await player.play(uri)
        if action == "seek":
            if uri and (
                player.state is None or player.state.track is None or player.state.track.uri != uri
            ):
                raise ValueError("Play this track before seeking from its lyrics.")
            return await player.seek(int(values["position_ms"]))
        if action == "volume":
            return await player.volume(int(values["percent"]))
        if action == "transfer":
            return await player.transfer(values["device"])
        if action == "shuffle":
            return await player.shuffle(values["enabled"] == "true")
        if action == "repeat":
            mode = values["mode"]
            if mode not in {"off", "context", "track"}:
                raise ValueError("Choose off, context or track")
            return await player.repeat(cast(Literal["off", "context", "track"], mode))
        if action == "sleep":
            seconds = float(values["seconds"])
            return await player.sleep_timer(seconds if seconds else None)
        if action == "queue_add":
            return await player.add_to_queue(uri)
        if action == "queue_remove":
            if player.state is None:
                raise ValueError("No active queue")
            occurrence = next(
                (track for track in player.state.next_tracks if track.uid == values["uid"]), None
            )
            if occurrence is None:
                raise ValueError("This queue occurrence is no longer present")
            return await player.remove_from_queue(occurrence)
        if action == "queue_replace":
            return await player.set_queue(_words(values["uris"]))
        player_calls = {
            "toggle": player.toggle,
            "pause": player.pause,
            "resume": player.resume,
            "next": player.next,
            "previous": player.previous,
            "restart": player.restart,
            "queue_clear": player.clear_queue,
            "video": player.switch_to_video,
            "audio": player.switch_to_audio,
        }
        if action in player_calls:
            return await player_calls[action]()
        raise ValueError("Unknown Studio operation")

    async def _queue_preview(self, player: Player) -> tuple[PlaybackTrack, ...]:
        """Resolve only visible queue rows; cache small display records instead of full models."""
        if player.state is None:
            return ()
        tracks = [
            item
            for item in player.state.next_tracks
            if item.uri.startswith(("spotify:track:", "spotify:episode:"))
        ][:8]
        unique = {track.uri: track for track in tracks}
        await asyncio.gather(*(self._queue_item(track) for track in unique.values()))
        return tuple(replace(track, **self._queue_metadata.get(track.uri, {})) for track in tracks)

    async def _queue_item(self, item: PlaybackTrack) -> PlaybackTrack:
        """Fill omitted track presentation fields once, retaining occurrence identity and order."""
        if (item.name and item.artist) or not item.uri.startswith("spotify:track:"):
            return item
        metadata = self._queue_metadata.get(item.uri)
        if metadata is None:
            try:
                track = await self.catalogue.get_track(item.uri)
                first = track.first_artist.items if track.first_artist else []
                others = track.other_artists.items if track.other_artists else []
                artists = ", ".join(
                    artist.profile.name for artist in (*first, *others) if artist.profile
                )
                cover = track.album_of_track.cover_art if track.album_of_track else None
                metadata = {
                    "name": track.name,
                    "artist": artists,
                    "image_url": (
                        cover.sources[0].url if cover and cover.sources else item.image_url
                    ),
                    "duration_ms": track.duration.total_milliseconds,
                }
            except (SpotAPIError, ValueError, TypeError):
                metadata = {"name": item.name or "Metadata unavailable"}
            self._queue_metadata[item.uri] = metadata
            if len(self._queue_metadata) > 64:
                self._queue_metadata.popitem(last=False)
        self._queue_metadata.move_to_end(item.uri)
        return replace(item, **metadata)


def _words(value: str) -> list[str]:
    """Split multi-resource form fields on whitespace or commas."""
    words = value.replace(",", " ").split()
    if not words:
        raise ValueError("Supply at least one item")
    if len(words) > 100:
        raise ValueError("Use at most 100 items per action")
    return words
