# Player and status

Create an authenticated client with `AsyncClient.from_cookies(cookie)`, then
pass it to `Player(client)`, `PlayerStatus(client)` or `LyricsClient(client)`.
Helpers borrow the client; its context owns authorization, renewal and transports.

```python
async with await AsyncClient.from_cookies(cookie) as client:
    player = Player(client)

    @player.event
    async def on_track_change(before, after):
        if after:
            print(after.artist, after.name)

    async with player.connect():
        print(player.devices)
        await player.wait_until_disconnected()
```

See the [typed runnable example](../examples/player.py). No playback commands
run automatically. A connection resolves regional hosts, waits for the dealer
connection ID, registers a control-only device, subscribes a hidden observer
and obtains a full snapshot. Exiting drains callbacks and timers, removes both
owned registrations, and closes the WebSocket. Your existing players remain.

For a long-running integration, `await player.start()` reconnects after transient
connection failures with bounded backoff. `await player.close()` stops it,
including from a listener. Authentication failures propagate immediately.
Use `is_ready`, `is_closed`, and `wait_until_ready()` to coordinate other tasks.

`state`, `devices` and `playback` are cached typed snapshots. Property reads
never make requests; `await player.refresh()` does. `state.position_ms`,
`remaining_ms` and `progress` advance locally while playing. `state.next_tracks` / `prev_tracks` are tuples
of `PlaybackTrack`. Cluster snapshots and device `replace_state` messages
remain separate. Media manifests and registration tokens are not retained.

Register one callback with `@player.event` and an `on_` name, or additional
callbacks with `@player.listen("track_change")`. Manual registration uses
`add_listener` / `remove_listener`. Pending listener tasks are bounded.
`await player.wait_for("pause", timeout=10)` returns the next matching state.
Supply a synchronous `check` predicate to filter events. Multiple event arguments
return a tuple; timeout, cancellation and shutdown remove temporary listeners.

| Event | Arguments |
| --- | --- |
| `ready`, `disconnect`, `reconnect`, `sleep_timer_finished` | None |
| `state_update` | Previous state (possibly None), new state |
| `track_change` | Previous track, new track (either may be None) |
| `devices_change` | Device tuple |
| `device_change` | Previous active ID, new active ID |
| `pause`, `resume`, `queue_change`, `options_change` | New state |
| `playback_update` | PlaybackUpdate |
| `volume_change` | Device, previous percentage, new percentage |
| `shuffle_change`, `repeat_change`, `speed_change`, `quality_change`, `context_change` | Previous value, new value |
| `position_change` | Previous reported milliseconds, new reported milliseconds |
| `library_change` | Track URI, saved flag; changes made through this Player |
| `command_ack` | Dealer acknowledgement ID |
| `error` | Transport, timer or listener exception |

`position_change` reports server snapshots, rather than a seek-only inference.
Track changes compare URI and occurrence UID, so richer metadata does not
announce the same song again. `state.quality`, `modes`, `restrictions` and
`allows("next")` expose what the current content and device support.

Inside the connection scope, `player.select(device)` chooses a target. The
active device is the default. `Player(client, device=..., source=...)` also
accepts explicit full playback IDs.

```python
await player.pause()
await player.resume()
await player.seek(30_000)
await player.volume(50)  # integer percentage, 0-100
await player.shuffle(True)
await player.repeat("context")  # off, context, track
await player.next()
await player.previous()
await player.play("spotify:album:4aawyAB9vmqN3uQ7FjRGTy", offset=2)
await player.add_to_queue("33XUHrCbrAW6me9ewdCZip")
await player.transfer(other_device, play=False)
```

`play()` accepts tracks, episodes, albums, playlists and artists; use
`position_ms` and either `offset` or `track` for a starting point. Bare IDs
mean tracks. `restart()` seeks to zero; `toggle()` toggles pause and resume.

Pass `PlaybackTrack` objects to `set_queue()` to reorder upcoming occurrences
without losing their UIDs. `remove_from_queue(occurrence)` removes exactly one;
passing a URI removes its first occurrence. `clear_queue()` removes manually
queued items while preserving context tracks and history. Queue updates carry
the last observed revision: wait for dealer state before issuing another edit.

`await player.sleep_timer(20 * 60)` pauses after twenty minutes.
Passing `None` cancels it. Timers belong to the connection and stop on exit.

`await player.is_liked()`, `like()` and `unlike()` use the current music track
by default. For batching, use `player.library` or `LikedTracks(client)` directly.
`await player.recents()` and `ListeningHistory(client)` return typed, dated
recents. These are Spotify's grouped played contexts and saved items, not an
exact timestamped stream history. Each item identifies its activity explicitly.

Transfers preserve paused state unless `play` is supplied. Mutations use one
attempt. Commands with `wait=True` complete on a matching dealer acknowledgement
or a fresh state proving the requested result. Without an acknowledgement ID,
they still require that state proof; otherwise they time out without replay.
Reconcile state after ambiguous failures or timeouts before retrying yourself.

For low-level experimentation, `command(endpoint, wait=False, **arguments)`
returns after HTTP acceptance. `wait_for_ack(id, timeout=10)` is available
separately. Acknowledgement history is bounded, including replies that arrive
before their HTTP response. Idempotent pause/resume/shuffle/repeat operations
avoid sending a command when the observed target state already matches.
Volume and transfer calls return after HTTP acceptance; verify the device snapshot
when subsequent work depends on the result. Play acknowledgement may precede
audio loading: use track/state events before depending on the loaded track.

For your own renderer, `register_device(name, client_version=...,
platform_identifier=..., capabilities=...)` returns a new full playback ID. Supply the renderer's SDK
version, platform identifier and actual capabilities. `report_state(id, state_ref=...,
sub_state=..., debug_source=...)` sends reports with increasing sequence
numbers. These registrations are removed on exit. SpotAPI does not decode
audio, consume manifests or send playback telemetry.

`deregister_device(full_id, observer_id=hobs_id, seq_num=...)` accepts the
identifiers separately. HOBS IDs are never inferred from playback IDs. Omit
`observer_id` to remove only a playback registration. When removing an
external registration, supply its current next sequence number.

## Premium lyrics

```python
lyrics = await LyricsClient(client).get(track_uri, image_url=cover_url)
for line in lyrics.at(position_ms):
    print(line.words)
```

The cover URL is optional. Spotify enforces account entitlements and lyric
availability; HTTP failures propagate. `Lyrics`, `LyricLine` and `LyricSyllable`
provide typed text, language, provider and timing data. Milliseconds are
integers, zero end times become None, and duplicate start times are retained.
`at()` returns all lines sharing the active timestamp; unsynchronized lyrics
return an empty tuple. See the [lyrics example](../examples/lyrics.py).

Offline tests replay sanitized versions of all four dealer captures and verify
outgoing request bodies. Authenticated live checks require a nonempty local
SPOTIFY_COOKIE. Playback commands and device removal are not run automatically
against a personal account.

To run these read-only private checks, set
SPOTIFY_COOKIE in your environment or local .env, then run
`python -m pytest --live=read tests/test_live_player.py -q`. The lyrics check requires a
Premium account. Scheduled public CI never enables this flag.

For an explicit playback check, open an existing player and run
`python -m pytest --live=all tests/test_live_controls.py -q`.
This changes permitted shuffle/repeat settings, adds and removes one queue occurrence, and briefly
plays a song to verify a timer-driven pause. It restores the original settings,
position and playback state in `finally`. Keep other apps from editing playback
while the test runs. This flag is never enabled by scheduled CI.
