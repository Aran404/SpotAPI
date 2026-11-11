# API layout

Import application-facing clients from `spotapi` and result dataclasses from
`spotapi.models`.

| Surface | Responsibility |
|---|---|
| `Public` | One-shot anonymous reads with automatic cleanup |
| `Private` | Own a cookie-authenticated account scope with automatic cleanup |
| `Catalogue` | Reuse one connection scope for typed catalogue operations |
| `AsyncClient` | Own HTTP, cookies, authorization and token refresh |
| `Account` | Compose borrowed account, library, profile, rankings and social helpers |
| `Library`, `LikedTracks`, `ListeningStats`, `ListeningHistory` | Independently reusable personal music operations |
| `Playlist`, `PlaylistHandler` | Existing playlist operations, creation and rootlist/folder management |
| `Profiles`, `Notifications`, `Blends` | Independently reusable account features |
| `PlayerStatus`, `Player`, `LyricsClient` | Observe playback, control existing devices and read entitled lyrics |
| `CaptchaChallenge`, `CaptchaRequired`, `CaptchaSolver` | Provider-neutral account challenge integration |
| `PasswordReset` | Explicit password recovery with caller-provided CAPTCHA responses |
| `AuthSession`, `close_query_clients` | Advanced authentication ownership and legacy shared-query shutdown |

`SearchResults`, `SpotifyResource` and `SpotAPIError` are also root exports because
application code commonly uses them directly.

`Queries` (`spotapi.queries`) and `QueryClient` (`spotapi.query`) remain explicit
lower-level imports. Transport implementations live in `spotapi.connection`.
They are available to expert integrations without crowding the normal entry point.

Account-page parsing, CSRF coordination, protobuf wire decoding, command-state
confirmation, and raw response normalization are implementation helpers. They do
not need root exports. They stay beside the features that use them rather than in
a growing, unrelated `utils` namespace. Bundle parsing has its own feature-specific
module. The small cache and weighted-selection helpers are not advertised as the
application API; unused random-account generators from the old utility module
were removed during the beta review.

Docstrings explain the operation, ownership and relevant side effects. Type
annotations carry the parameter and return shapes; prose does not repeat them
unless a constraint or protocol detail needs explanation. Overload declarations
share their implementation's documentation.
