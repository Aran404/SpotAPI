---
description: Supported Spotify Connect controls, verification and device boundaries.
---

# Player capabilities

SpotAPI is a **remote controller** for an existing Spotify player. It can read
current playback, respond to changes and send controls to a selected device.
It cannot decode protected music, replace a Spotify audio player or synchronize
speakers. A Spotify account and a supported active device are required for
player commands; availability varies by account and device.

## Existing-player controls

| Capability | API | Important behavior |
|---|---|---|
| State and devices | `Player.state`, `devices`, `refresh()` | State is cached; `refresh()` fetches a new snapshot |
| Play and transport | `play()`, `pause()`, `resume()`, `next()`, `previous()` | Controls an existing Spotify device; does not render audio |
| Position and volume | `seek()`, `restart()`, `volume()` | Actions can be restricted by the current context |
| Playback settings | `shuffle()`, `repeat()` | Device and content determine which operations are allowed |
| Device routing | `select()`, `transfer()` | `select()` only changes the local target; `transfer()` requests an actual transfer |
| Queue | `add_to_queue()`, `set_queue()`, `remove_from_queue()`, `clear_queue()` | Some edits require an observed queue revision |
| Personal controls | `like()`, `unlike()`, `is_liked()`, `recents()` | Requires account access; recents are not an exact listening timeline |
| Lyrics | `LyricsClient.get()`, `Lyrics.at()` | Entitlement and per-track availability apply |
| Events | `listen()`, `event()`, `wait_for()` | State, track, device, queue and error events are available |

See [Player and status](player.md) for runnable examples, method arguments,
resource ownership and event names.

## Reliability and confirmation

Commands do not silently retry after ambiguous errors. SpotAPI accepts a dealer
acknowledgement or a newly observed state proving supported actions. An
acknowledgement can arrive before audio is actually loaded; observe the player
state before depending on the next song. The client handles reconnects, but
notifications missed while disconnected are not replayed.

Playback validation has covered desktop scenarios and captured Web Player
requests. Browser-based playback has occasionally accepted commands without
reaching the requested state. **Do not advertise identical behavior for every
device or Free-account setup without testing it.**

## Boundaries

Spotify Connect is not an audio decoding engine. Audio playback, DRM,
normalization, crossfade and speaker synchronization are outside SpotAPI's
scope. Features such as Smart Shuffle, device renaming and podcast playback
speed do not have verified wrappers. Public catalogue data requires no developer
key; authenticated playback can still have account and device restrictions.

For the exact dated observations behind these statements, see the
[maintainer playback snapshot](https://github.com/Aran404/SpotAPI/blob/main/docs/development/player-verification-2026-11-10.md).
For a clean environment or missing playback device, use
[troubleshooting](troubleshooting.md).
