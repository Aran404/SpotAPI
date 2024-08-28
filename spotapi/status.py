from typing import Dict, Any, Callable, List, ParamSpec, TypeVar
from spotapi.types.annotations import enforce
from spotapi.types.data import PlayerState, Devices, Track
from spotapi.login import Login
from spotapi.websocket import WebsocketStreamer
import threading
import functools

R = TypeVar("R")
P = ParamSpec("P")


@enforce
class PlayerStatus(WebsocketStreamer):
    """
    A class used to represent the current state of the player.

    Parameters
    ----------
    login : Login
        The login instance used for authentication.
    s_device_id : Optional[str], optional
        The device ID to use for the player. If None, a new device ID will be generated.
    """

    _device_dump: Dict[str, Any] | None = None
    _state: Dict[str, Any] | None = None
    _devices: Dict[str, Any] | None = None

    def __init__(self, login: Login, s_device_id: str | None = None) -> None:
        super().__init__(login)

        if s_device_id:
            self.device_id = s_device_id

        # Register current device with Spotify
        self.register_device()

    def renew_state(self) -> None:
        self._device_dump = self.connect_device()
        self._state = self._device_dump["player_state"]
        self._devices = self._device_dump["devices"]

    @functools.cached_property
    def saved_state(self) -> PlayerState:
        """Gets the last saved state of the player."""
        if self._state is None:
            self.renew_state()

        if self._state is None:
            raise ValueError("Could not get player state")

        return PlayerState.from_dict(self._state)

    @property
    def state(self) -> PlayerState:
        """Gets the current state of the player."""
        self.renew_state()

        if self._state is None:
            raise ValueError("Could not get player state")

        return PlayerState.from_dict(self._state)

    @functools.cached_property
    def saved_device_ids(self) -> Devices:
        """Gets the last saved device IDs of the player."""
        if self._devices is None:
            self.renew_state()

        if self._devices is None:
            raise ValueError("Could not get devices")

        if (
            self._device_dump is None
            or self._device_dump.get("active_device_id") is None
        ):
            raise ValueError("Could not get active device ID")

        return Devices.from_dict(self._devices, self._device_dump["active_device_id"])

    @property
    def device_ids(self) -> Devices:
        """Gets the current device IDs of the player."""
        self.renew_state()

        if self._devices is None:
            raise ValueError("Could not get devices")

        return Devices.from_dict(
            self._devices,
            self._device_dump.get("active_device_id") if self._device_dump else None,
        )

    @property
    def active_device_id(self) -> str:
        """Gets the active device ID of the player."""
        self.renew_state()

        if (
            self._device_dump is None
            or self._device_dump.get("active_device_id") is None
        ):
            raise ValueError("Could not get active device ID")

        return self._device_dump["active_device_id"]

    @property
    def next_song_in_queue(self) -> Track | None:
        """Gets the next song in the queue."""
        state = self.state

        if len(state.next_tracks) <= 0:
            return None

        return state.next_tracks[0]

    @property
    def next_songs_in_queue(self) -> List[Track]:
        """Gets the next songs in the queue."""
        state = self.state
        return state.next_tracks

    @property
    def last_played(self) -> Track | None:
        """Gets the last played track."""
        state = self.state

        if len(state.prev_tracks) <= 0:
            return None

        return state.prev_tracks[-1]

    @property
    def last_songs_played(self) -> List[Track]:
        """Gets the last played songs."""
        state = self.state
        return state.prev_tracks


@enforce
class EventManager(PlayerStatus):
    def __init__(self, login: Login, s_device_id: str | None = None) -> None:
        super().__init__(login, s_device_id)
        self._current_state = self.state  # Need this to activate websocket

        self.wlock = threading.Lock()
        self._subscriptions: Dict[str, List[Callable[..., Any]]] = {}

        self.listener = threading.Thread(target=self._listen, daemon=True)
        self.listener.start()

    def _subscribe_callable(self, event: str, func: Callable[..., Any]) -> None:
        with self.wlock:
            if event not in self._subscriptions:
                self._subscriptions[event] = []

            if func not in self._subscriptions[event]:
                self._subscriptions[event].append(func)
            else:
                raise ValueError(
                    f"Function {func.__name__} is already subscribed to event '{event}'"
                )

    def subscribe(self, event: str) -> Callable[[Callable[P, R]], Callable[P, R]]:
        """
        Decorator to subscribe a function to a Spotify websocket event.
        """

        def decorator(func: Callable[P, R]) -> Callable[P, R]:
            @functools.wraps(func)
            def wrapped(*args: P.args, **kwargs: P.kwargs) -> R:
                result = func(*args, **kwargs)
                return result

            self._subscribe_callable(event, wrapped)
            return wrapped

        return decorator

    def _emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """
        Emit an event, triggering all subscribed functions.
        Should only be called from the WebsocketStreamer thread.
        """
        if event in self._subscriptions:
            for func in self._subscriptions[event]:
                func(*args, **kwargs)

    def unsubscribe(self, event: str, func: Callable[..., Any]) -> None:
        """Unsubscribe a function from an event."""
        with self.wlock:
            if event in self._subscriptions:
                self._subscriptions[event].remove(func)

    def _listen(self) -> None:
        while True:
            event = self.get_packet()
            if event is None or event.get("payloads") is None:
                continue

            for payload in event["payloads"]:
                self._emit(payload["update_reason"], payload)
