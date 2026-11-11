"""Connect capture replay, command contracts and scoped device ownership."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncGenerator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Self
from unittest.mock import AsyncMock, Mock

import pytest
import wreq

from spotapi import AsyncClient, LyricsClient, Player, PlayerStatus
from spotapi.connect import ConnectEndpoints
from spotapi.connection import HTTPClient, Response
from spotapi.datastruct import ObjectDict
from spotapi.models import PlaybackTrack, PlaybackUpdate, PlayerState
from spotapi.session import AccessToken, AuthSession
from spotapi.types import BaseClientError, HTTPError

FIXTURES = Path(__file__).parent / "fixtures" / "connect"


def packet(number: int) -> dict[str, Any]:
    return json.loads((FIXTURES / f"message-{number}.json").read_text(encoding="utf-8"))


def response(body: Mapping[str, Any] | None = None, *, status: int = 200) -> Mock:
    return Mock(
        spec=Response,
        json=ObjectDict(body) if body is not None else None,
        ok=status < 400,
        status_code=Mock(as_int=Mock(return_value=status)),
    )


@pytest.fixture
def session() -> Mock:
    client = Mock(spec=AsyncClient)
    client.get = AsyncMock(
        return_value=response(
            {
                "dealer-g2": ["dealer.test.spotify.com:443"],
                "spclient": ["client.test.spotify.com:443"],
            }
        )
    )
    client.put = AsyncMock(return_value=response(packet(2)["payloads"][0]["cluster"]))
    client.post = AsyncMock(return_value=response({"initial_seq_num": 1, "ack_id": "fixture"}))
    client.delete = AsyncMock(return_value=response())
    client.protocols.http.delete = AsyncMock(return_value=response())

    return Mock(
        spec=AuthSession,
        client=client,
        authorized_headers={"authorization": "Bearer test"},
        token=Mock(access_token="test-token"),
    )


class Socket:
    instances: list[Socket] = []

    def __init__(self, *, http_client: HTTPClient) -> None:
        self.callbacks: dict[str, Callable[..., Awaitable[object]]] = {}
        self.closed = False

        self.instances.append(self)

    async def close(self) -> None:
        self.closed = True

    def start_pinging(self, *, interval: float) -> None:
        assert interval == 30

    def event(
        self, name: str
    ) -> Callable[[Callable[..., Awaitable[object]]], Callable[..., Awaitable[object]]]:
        def decorate(
            callback: Callable[..., Awaitable[object]],
        ) -> Callable[..., Awaitable[object]]:
            self.callbacks[name] = callback

            return callback

        return decorate

    @asynccontextmanager
    async def connect(self, url: str, *, headers: dict[str, str]) -> AsyncGenerator[Self, None]:
        assert url.startswith("wss://dealer.test.spotify.com:443/")

        await self.callbacks["message"](
            wreq.Message.from_text(
                json.dumps({"headers": {"Spotify-Connection-Id": "connection"}})
            )
        )
        await self.callbacks["message"](
            wreq.Message.from_text(json.dumps({"payloads": [{"ack_id": "fixture"}]}))
        )

        try:
            yield self
        finally:
            self.closed = True


async def test_all_captures_parse_and_emit_typed_events(session: Mock) -> None:
    status = PlayerStatus(session)
    updates: list[PlaybackUpdate] = []
    states: list[PlayerState] = []

    @status.event
    async def on_playback_update(value: PlaybackUpdate) -> None:
        updates.append(value)

    @status.listen("state_update")
    async def changed(before: PlayerState | None, after: PlayerState) -> None:
        states.append(after)

    for number in (1, 2, 3, 4):
        status.process_message(packet(number))

    await asyncio.sleep(0)

    assert len(updates) == len(states) == 2
    assert updates[0].track is not None and updates[0].track.name == "Empty"
    assert updates[1].track is not None and updates[1].track.name == "WRLD On Drugs"
    assert updates[0].position_ms is None
    assert all(update.track and update.track.name and update.track.uri for update in updates)
    assert status.state is not None and status.state.track is not None
    assert status.state.track.name
    assert len(status.devices) == 2
    assert any(device.is_active for device in status.devices)

    await status._events.close()


async def test_old_snapshot_does_not_replace_new_state(session: Mock) -> None:
    status = PlayerStatus(session)

    status.process_message(packet(3))

    current = status.state
    old = packet(2)
    old["payloads"][0]["cluster"]["timestamp"] = 1

    status.process_message(old)

    assert status.state is current


async def test_connection_subscribes_and_cleans_only_its_observer(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    status = PlayerStatus(session)

    async with status.connect():
        assert status.connection_id == "connection"
        options = session.client.put.call_args.kwargs

        assert options["headers"]["x-spotify-connection-id"] == "connection"
        assert options["max_attempts"] == 1
        assert options["json"]["device"]["device_info"]["capabilities"]["can_be_player"] is False

    assert session.client.protocols.http.delete.await_count == 2

    assert (
        session.client.protocols.http.delete.await_args_list[0]
        .args[0]
        .endswith(status.observer_id)
    )
    assert Socket.instances[-1].closed
    session.client.close.assert_not_called()


async def test_commands_transfer_and_volume_are_single_attempt(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    player = Player(session, device="target", source="source")

    async with player.connect():
        await player.resume()

        command = session.client.post.call_args

        assert command.args[0].endswith("/player/command/from/source/to/target")
        assert command.kwargs["json"]["command"]["endpoint"] == "resume"
        assert command.kwargs["max_attempts"] == 1

        await player.volume(50)

        assert session.client.put.call_args.kwargs["json"]["volume"] == 32768

        await player.seek(12000)

        seek = session.client.post.call_args.kwargs["json"]["command"]

        assert seek["value"] == seek["position"] == 12000
        assert seek["relative"] == "beginning"

        await player.transfer("other", play=False)

        assert session.client.post.call_args.kwargs["json"]["transfer_options"] == {
            "restore_paused": "pause"
        }
        assert player.target_device_id == "other"


async def test_owned_device_registration_reporting_and_removal(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    player = Player(session, device="existing")

    async with player.connect():
        id = await player.register_device(
            "Renderer",
            client_version="test",
            platform_identifier="test-platform",
            capabilities={"audio_podcasts": True},
        )

        await player.report_state(
            id, state_ref=None, sub_state={"playback_speed": 0}, debug_source="test"
        )

        first = session.client.put.call_args.kwargs["json"]["seq_num"]

        await player.report_state(id, state_ref=None, sub_state={}, debug_source="test")

        assert session.client.put.call_args.kwargs["json"]["seq_num"] == first + 1

    delete = session.client.protocols.http.delete.call_args

    assert delete.args[0].endswith("/track-playback/v1/devices/" + id)
    assert delete.kwargs["json"]["seq_num"] == first + 2
    assert delete.kwargs["max_attempts"] == 1


async def test_hobs_is_not_accepted_as_a_playback_device(session: Mock) -> None:
    with pytest.raises(ValueError, match="HOBS"):
        Player(session).select("hobs_observer")

    with pytest.raises(ValueError):
        await Player(session).volume(101)


async def test_lyrics_decode_timestamps_and_duplicate_lines(session: Mock) -> None:
    session.client.get.side_effect = [
        response(
            {
                "dealer-g2": ["dealer.test.spotify.com:443"],
                "spclient": ["client.test.spotify.com:443"],
            }
        ),
        response(
            {
                "lyrics": {
                    "syncType": "LINE_SYNCED",
                    "language": "en",
                    "lines": [
                        {"startTimeMs": "1000", "endTimeMs": "0", "words": "First"},
                        {"startTimeMs": "1000", "endTimeMs": "0", "words": "Second"},
                        {"startTimeMs": "2000", "words": "Third"},
                    ],
                }
            }
        ),
    ]

    lyrics = await LyricsClient(session).get(
        "spotify:track:track", image_url="https://i.scdn.co/image/cover"
    )

    assert not lyrics.at(999)
    assert [line.words for line in lyrics.at(1000)] == ["First", "Second"]
    assert lyrics.at(2000)[0].words == "Third"
    assert lyrics.lines[0].end_time_ms is None
    assert "/image/https%3A%2F%2Fi.scdn.co%2Fimage%2Fcover" in session.client.get.call_args.args[0]


async def test_resolver_rejects_untrusted_hosts(session: Mock) -> None:
    session.client.get.return_value = response({"dealer-g2": ["example.com:443"], "spclient": []})

    with pytest.raises(BaseClientError, match="invalid host"):
        await ConnectEndpoints.resolve(session)


async def test_cancellation_preserved_when_observer_cleanup_fails(
    session: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    session.client.protocols.http.delete.side_effect = ValueError("cleanup failed")

    with pytest.raises(asyncio.CancelledError) as raised:
        async with PlayerStatus(session).connect():
            raise asyncio.CancelledError()

    assert isinstance(raised.value.__cause__, ValueError)
    assert Socket.instances[-1].closed


async def test_cookie_client_owns_token_renewal(monkeypatch: pytest.MonkeyPatch) -> None:
    refresh: asyncio.Task[None] | None = None

    async def authorize(self: AuthSession) -> AccessToken:
        nonlocal refresh
        refresh = asyncio.create_task(asyncio.sleep(60))
        self._refresh_task = refresh
        self._token = AccessToken("client", "access", 0, "client-token")

        return self._token

    monkeypatch.setattr(AuthSession, "authorize", authorize)

    async with await AsyncClient.from_cookies("sp_dc=test") as client:
        assert Player(client).session is client.session
        assert refresh is not None and not refresh.done()

    assert refresh is not None and refresh.done()

    with pytest.raises(RuntimeError, match="not open"):
        _ = client.protocols


async def test_listeners_stop_before_observer_is_removed(
    session: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    player = Player(session)
    started, stopped = asyncio.Event(), asyncio.Event()

    @player.event
    async def on_ready() -> None:
        started.set()

        try:
            await asyncio.Future[None]()
        finally:
            stopped.set()

    async def remove(*args: object, **kwargs: Any) -> Mock:
        assert stopped.is_set()

        with pytest.raises(RuntimeError, match="not connected"):
            await player.resume()

        return response()

    session.client.protocols.http.delete.side_effect = remove

    async with player.connect():
        await started.wait()

    assert stopped.is_set()


async def test_external_device_and_hobs_are_removed_by_their_exact_ids(
    session: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    async with Player(session).connect() as player:
        await player.deregister_device("full-device-id", observer_id="hobs_short-id", seq_num=7)

        observer = session.client.delete.await_args_list[0]
        device = session.client.protocols.http.delete.await_args_list[-1]

        assert observer.args[0].endswith("/connect-state/v1/devices/hobs_short-id")
        assert device.args[0].endswith("/track-playback/v1/devices/full-device-id")
        assert device.kwargs["json"]["seq_num"] == 7
        assert observer.kwargs["max_attempts"] == device.kwargs["max_attempts"] == 1


async def test_metadata_enrichment_is_not_a_track_change(session: Mock) -> None:
    status = PlayerStatus(session)
    changes: list[tuple[PlaybackTrack | None, PlaybackTrack | None]] = []

    @status.event
    async def on_track_change(before: PlaybackTrack | None, after: PlaybackTrack | None) -> None:
        changes.append((before, after))

    original = packet(2)

    status.process_message(original)

    original["payloads"][0]["cluster"]["player_state"]["track"]["metadata"][
        "title"
    ] = "Updated title"

    status.process_message(original)
    await asyncio.sleep(0)

    assert not changes
    assert status.state and status.state.track and status.state.track.name == "Updated title"

    await status._events.close()


async def test_wait_for_filters_and_removes_completed_listener(session: Mock) -> None:
    status = PlayerStatus(session)

    def matches(before: str, after: str) -> bool:
        return after == "wanted"

    received = asyncio.create_task(status.wait_for("device_change", check=matches, timeout=1))

    await asyncio.sleep(0)
    status._events.dispatch("device_change", "old", "ignored")
    await asyncio.sleep(0)

    assert not received.done()

    status._events.dispatch("device_change", "old", "wanted")

    assert await received == ("old", "wanted")
    assert not status._waiters
    assert "device_change" not in status._events._listeners

    await status._events.close()


async def test_listener_failure_reaches_on_error_without_interrupting_other_listeners(
    session: Mock,
) -> None:
    status = PlayerStatus(session)
    reported: asyncio.Future[Exception] = asyncio.get_running_loop().create_future()
    healthy = asyncio.Event()
    failure = ValueError("listener failed")

    @status.event
    async def on_ready() -> None:
        raise failure

    @status.listen("ready")
    async def another_listener() -> None:
        healthy.set()

    @status.event
    async def on_error(error: Exception) -> None:
        reported.set_result(error)

    status._events.dispatch("ready")

    assert await asyncio.wait_for(reported, 1) is failure
    assert healthy.is_set()

    await status._events.close()


async def test_wait_for_timeout_and_check_failure_leave_no_listeners(session: Mock) -> None:
    status = PlayerStatus(session)

    with pytest.raises(TimeoutError):
        await status.wait_for("ready", timeout=0.001)

    def invalid_check() -> bool:
        raise ValueError("invalid predicate")

    received = asyncio.create_task(status.wait_for("ready", check=invalid_check, timeout=1))

    await asyncio.sleep(0)
    status._events.dispatch("ready")

    with pytest.raises(ValueError, match="invalid predicate"):
        await received

    assert not status._waiters
    assert not status._events._listeners

    await status._events.close()


async def test_managed_listener_can_close_from_ready_callback(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    status = PlayerStatus(session)
    completed = asyncio.Event()

    @status.event
    async def on_ready() -> None:
        await status.close()
        completed.set()

    await asyncio.wait_for(status.start(reconnect=False), 1)
    await asyncio.wait_for(completed.wait(), 1)

    assert status.is_closed and not status.is_ready
    assert session.client.protocols.http.delete.await_count == 2
    assert Socket.instances[-1].closed


async def test_managed_listener_does_not_retry_rejected_authorization(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    session.client.get.side_effect = HTTPError("Unauthorized", status_code=401)
    status = PlayerStatus(session)

    with pytest.raises(HTTPError):
        await status.start()

    assert session.client.get.await_count == 1
    assert status.is_closed


async def test_managed_listener_reconnects_and_can_stop_from_reconnect_callback(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    status = PlayerStatus(session)
    connections = 0

    @status.event
    async def on_ready() -> None:
        nonlocal connections
        connections += 1

        if connections == 1:
            status._disconnected.set()

    @status.event
    async def on_reconnect() -> None:
        await status.close()

    await asyncio.wait_for(status.start(), 3)

    assert connections == 2
    assert status.is_closed
    assert session.client.protocols.http.delete.await_count == 4


async def test_close_cancels_pending_event_waiters(session: Mock) -> None:
    status = PlayerStatus(session)
    waiting = asyncio.create_task(status.wait_for("track_change"))

    await asyncio.sleep(0)
    await status.close()

    with pytest.raises(asyncio.CancelledError):
        await waiting

    assert not status._waiters
    assert "track_change" not in status._events._listeners


async def test_command_acknowledgement_handles_early_and_late_replies(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    async with Player(session).connect() as player:

        async def early_reply(*args: object, **kwargs: Any) -> Mock:
            player.process_message({"payloads": [{"ack_id": "early"}]})

            return response({"ack_id": "early"})

        session.client.post.side_effect = early_reply

        await player.command("resume", timeout=0.1)

        session.client.post.side_effect = None
        session.client.post.return_value = response({"ack_id": "late"})
        pending = asyncio.create_task(player.command("resume", timeout=1))

        await asyncio.sleep(0)

        assert not pending.done()

        player.process_message({"payloads": [{"ack_id": "unrelated"}]})
        await asyncio.sleep(0)

        assert not pending.done()

        player.process_message({"payloads": [{"ack_id": "late"}]})
        await pending


async def test_unacknowledged_command_is_not_replayed(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    async with Player(session).connect() as player:
        session.client.post.reset_mock()
        session.client.post.return_value = response({"ack_id": "missing"})

        with pytest.raises(TimeoutError):
            await player.command("resume", timeout=0.001)

        assert session.client.post.await_count == 1

        with pytest.raises(ValueError, match="timeout"):
            await player.command("resume", timeout=-1)

        assert session.client.post.await_count == 1


async def test_shutdown_wakes_command_waiters_and_ack_history_is_bounded(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)

    async with Player(session).connect() as player:
        for number in range(200):
            player.process_message({"payloads": [{"ack_id": str(number)}]})

        assert len(player._acks) == 128

        waiting = asyncio.create_task(player.wait_for_ack("missing"))

        await asyncio.sleep(0)
        await player.close()

        with pytest.raises(RuntimeError, match="closed"):
            await waiting


async def test_controller_keepalive_failure_disconnects_and_preserves_cause(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    session.client.post.return_value = response(
        {"initial_seq_num": 8, "device_keep_alive_update_seconds": 1}
    )
    status = PlayerStatus(session)

    async with status.connect():
        controller = status._controller

        assert controller is not None
        assert status._controller_task is not None

        failure = ConnectionError("connection lost")
        report = AsyncMock(side_effect=failure)
        monkeypatch.setattr(type(controller), "report", report)
        controller.keep_alive_seconds = 0

        with pytest.raises(BaseClientError) as caught:
            await asyncio.wait_for(status.wait_until_disconnected(), 2)

        assert caught.value.__cause__ is status._error
        assert status._error is not None and status._error.__cause__ is failure
        assert report.await_args is not None
        assert report.await_args.kwargs["debug_source"] == "keep_alive"

    assert status._controller_task is None


async def test_queue_removal_preserves_duplicate_occurrences_and_revision(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    cluster = packet(2)["payloads"][0]["cluster"]
    uri = "spotify:episode:33XUHrCbrAW6me9ewdCZip"
    cluster["player_state"]["next_tracks"] = [
        {"uri": uri, "uid": "first", "provider": "queue"},
        {"uri": uri, "uid": "second", "provider": "queue"},
        {"uri": "spotify:track:33XUHrCbrAW6me9ewdCZip", "provider": "context"},
    ]
    cluster["player_state"]["queue_revision"] = "revision"
    session.client.put.return_value = response(cluster)

    async with Player(session).connect() as player:
        assert player.state is not None

        await player.remove_from_queue(player.state.next_tracks[1])

        command = session.client.post.await_args.kwargs["json"]["command"]

        assert command["endpoint"] == "set_queue"
        assert command["queue_revision"] == "revision"
        assert [track.get("uid") for track in command["next_tracks"]] == ["first", None]
        assert command["next_tracks"][0]["metadata"] == {"is_queued": "true"}

        await player.remove_from_queue(uri)

        command = session.client.post.await_args.kwargs["json"]["command"]

        assert command["next_tracks"][0]["uid"] == "second"


async def test_sleep_timer_pauses_and_connection_cleanup_cancels_replacement(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    player = Player(session)
    pause = AsyncMock()
    monkeypatch.setattr(Player, "pause", pause)

    async with player.connect():
        finished = asyncio.create_task(player.wait_for("sleep_timer_finished", timeout=1))

        await player.sleep_timer(0.001)
        await finished
        pause.assert_awaited_once()
        await player.sleep_timer(60)

        pending = player._sleep_task

        assert pending is not None and not pending.done()
        assert player.sleep_timer_remaining is not None

    assert pending.cancelled()
    assert player.sleep_timer_remaining is None


def test_position_accounts_for_snapshot_age_and_stops_when_paused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.playback.time.monotonic", lambda: 100.0)
    cluster: dict[str, Any] = {
        "timestamp": "3000",
        "server_timestamp_ms": "5000",
        "player_state": {
            "timestamp": "2000",
            "position_as_of_timestamp": "10000",
            "duration": "20000",
            "is_playing": True,
            "is_paused": False,
            "playback_speed": 1.5,
        },
    }
    state = replace(PlayerState.from_cluster(cluster), received_at=100.0)

    assert state.position_ms == 14500

    monkeypatch.setattr("spotapi.playback.time.monotonic", lambda: state.received_at + 2)

    assert state.position_ms == 17500

    cluster["player_state"]["is_paused"] = True
    paused = PlayerState.from_cluster(cluster)

    assert paused.position_ms == 10000
    assert not paused.is_playing


async def test_video_signals_use_advertised_player_capabilities(
    session: Mock, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    player = Player(session)
    async with player.connect():
        assert player.state is not None
        player.state = replace(player.state, signals=("switch-to-video",))
        await player.switch_to_video()
        command = session.client.post.call_args.kwargs["json"]["command"]
        assert command["endpoint"] == "signal" and command["signal_id"] == "switch-to-video"
        with pytest.raises(ValueError, match="does not advertise"):
            await player.switch_to_audio()


async def test_default_command_source_is_the_existing_active_player(
    session: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    player = Player(session)
    async with player.connect():
        assert player.state is not None and player.state.active_device_id
        await player.command("resume")
        url = session.client.post.call_args.args[0]
        active = player.state.active_device_id
        assert url.endswith(f"/player/command/from/{active}/to/{active}")


@pytest.mark.parametrize("body", [{"ack_id": "not-delivered"}, {}, {"ack_id": ""}])
async def test_missing_ack_can_complete_only_after_a_proven_state_change(
    session: Mock,
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, str],
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    player = Player(session)
    async with player.connect():
        before = player.state
        assert before is not None
        session.client.post.return_value = response(body)
        task = asyncio.create_task(player.command("pause", timeout=1))
        await asyncio.sleep(0)
        assert not task.done()
        async with asyncio.timeout(1):
            while not player._waiters:
                await asyncio.sleep(0)
        update = packet(2)
        cluster = update["payloads"][0]["cluster"]
        cluster["timestamp"] = before.timestamp + 1
        cluster["player_state"]["is_paused"] = True
        cluster["player_state"]["is_playing"] = False
        player.process_message(update)
        await task
        assert not player._waiters


@pytest.mark.parametrize("body", [{"ack_id": "never-delivered"}, {}, {"ack_id": ""}])
async def test_missing_ack_and_unchanged_state_fail_without_replaying(
    session: Mock,
    monkeypatch: pytest.MonkeyPatch,
    body: dict[str, str],
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    player = Player(session)
    async with player.connect():
        session.client.post.return_value = response(body)
        session.client.post.reset_mock()
        with pytest.raises(TimeoutError):
            await player.command("signal", signal_id="unknown", timeout=0.02)
        session.client.post.assert_awaited_once()
        assert not player._waiters


async def test_disconnected_observer_stops_claiming_readiness_and_sending_commands(
    session: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("spotapi.status.WebSocketClient", Socket)
    player = Player(session)
    async with player.connect():
        assert player.is_ready
        session.client.post.reset_mock()
        player._disconnected.set()
        assert not player.is_ready
        with pytest.raises(RuntimeError, match="not connected"):
            await player.next()
        session.client.post.assert_not_awaited()
