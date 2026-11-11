# Player coverage

Reviewed against Spotify's [Web API player reference](https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback),
[Web Playback SDK reference](https://developer.spotify.com/documentation/web-playback-sdk/reference),
the supplied dealer captures and live Web Player requests on 2026-11-10.
The event interface follows the decorator and predicate patterns documented by
[discord.py](https://discordpy.readthedocs.io/en/stable/api.html#discord.Client.wait_for).

## Existing players

| Capability | SpotAPI | Verification |
| --- | --- | --- |
| Current playback and available devices | `state`, `devices`, `refresh()` | Live snapshots and capture replay |
| Play a link or context | `play(value, position_ms=..., offset=..., track=...)` | Direct track and context restoration live; offsets validated offline |
| Pause, resume, toggle, restart, seek | `pause`, `resume`, `toggle`, `restart`, `seek` | Pause/resume events, seek/restart live; toggle delegates tested controls |
| Next / previous | `next`, `previous` | Both live; previous may restart the current song according to Spotify |
| Shuffle and three repeat modes | `shuffle`, `repeat` | Live controls and resulting dealer state |
| Volume | `volume(percent)`, `Device.volume_percent` | Live change and restoration |
| Select and transfer | `select`, `transfer` | Transfer between existing players live; original device restored |
| Read / append / replace queue | `state.next_tracks`, `add_to_queue`, `set_queue` | Live append and occurrence removal |
| Remove one / reorder / clear manual queue | `remove_from_queue`, `set_queue`, `clear_queue` | UID/revision preservation offline; removal live |
| Liked tracks | `is_liked`, `like`, `unlike`, `LikedTracks` | Live save/check/remove with original saved status restored |
| Dated recents | `recents`, `ListeningHistory` | Typed live response; identity/date parsing offline |
| Premium lyrics | `LyricsClient.get`, `Lyrics.at` | Live availability and typed timing; duplicate timestamps offline |
| Sleep timer | `sleep_timer`, `sleep_timer_remaining` | Real timer-driven pause event live; expiration and cleanup offline |

Playback commands accept a matching dealer acknowledgement or a fresh state proving
the requested result. Hidden/browser controllers can omit ACKs. Mutations are never
replayed, and actions restricted by the current context are rejected locally. Volume and transfer return after HTTP acceptance. Observe dealer state to
confirm the resulting behavior and wait for a loaded track after play requests.
Raw `command(..., wait=False)` can opt out explicitly.
Queue revisions can become stale after another command or another app changes
the queue. Mutations are never replayed automatically after an ambiguous failure.
The live control regression confirms shuffle/repeat changes, a duplicate queue
occurrence's insertion/removal, timer-driven pause, and restoration. Seek sends
both position fields with an absolute origin for Web Player compatibility.
Position projection uses Spotify's server time and position anchor before
advancing with the local monotonic clock.
The desktop passed the queue/options/timer regression twice consecutively.
Browser validation was intermittent: some acknowledged commands did not converge
to the requested state. The cause remains unresolved; browser control should be
treated as experimental. Next/previous, loaded direct
play, context/track restoration and volume were subsequently verified on desktop;
the original browser device was restored, paused, after those checks.
A transfer back returned HTTP 502 during validation; a fresh snapshot was used
to reconcile and restore the original device. Exact listening history is not
reversible when testing next/previous or playing another context.

Recents contain grouped contexts and saved actions with calendar dates, rather
than an exact timestamp for every play. Lyrics remain dependent on entitlement,
market and track availability. Existing playback must run on a real Spotify
device; SpotAPI is a controller, not an audio decoder.

## Events and ownership

`event`, `listen`, `add_listener`, `remove_listener` and `wait_for` support
reactive integrations. Events cover readiness, disconnection/reconnection,
state, track occurrence, queue, active device, device list, volume, shuffle,
repeat, speed, quality, context, reported position, local library changes and
sleep timer completion. The [guide](player.md) lists exact arguments.

`connect()` owns one connection scope. `start()` reconnects on transient failures;
authentication errors stop immediately. Shutdown cancels owned callbacks,
waiters, keep-alives and timers, removes the owned observer and control-only
registration, and closes the socket. The supplied authenticated client remains
the caller's responsibility. A native silent-WebSocket regression test covers
idle reads blocking send/close in wreq's serialized command actor.

Advanced integrations can use `RegisteredDevice` from `spotapi.devices`
directly or the Player registration/report helpers with their renderer's actual
capabilities. Playback and HOBS observer IDs remain separate. Automatic cleanup
only removes registrations created by the instance.

## Deliberate limits

Browser `activateElement`, browser audio decoding and DRM initialization belong
to the Web Playback SDK. Audio quality is observed, not remotely forced.
Crossfade, normalization, equalizer, remote device renaming, Smart Shuffle,
autoplay configuration and podcast speed controls have no verified wrapper here.
The raw `command()` escape hatch does not imply these operations are supported.

Official OAuth Web API methods are not interchangeable with cookie-authenticated
Web Player endpoints. The initial official device-list probe returned HTTP 429;
probing that route stopped. SpotAPI uses the verified Connect/Pathfinder routes
described here, without promising that unofficial clients are undetectable.

## Useful next examples

The best next hooks use the existing typed APIs: a live lyrics companion with
album artwork, a queue editor that preserves duplicate occurrences, and a
playlist discovery game that queues a choice and saves favorites. Keep these
optional examples so the core library retains its single transport dependency.
These are product ideas, not shipped features or a prediction of star growth.

## Studio follow-up

The 2026-11-10 release pass also checked the current Spotify SDK implementation at
[its deployed embedded client](https://sdk.scdn.co/embedded/index.js). Hidden
controllers can omit dealer ACKs, so known commands may complete on a fresh snapshot
proving their result. Unsupported context actions are rejected locally; an autoplay
or radio context can explicitly disable shuffle and repeat. The current live control
suite verifies queue changes and a timer-driven pause, and changes shuffle/repeat
only when Spotify permits them. See the [release checks](release-2.0.0.md).
