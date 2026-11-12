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

The internal `_protocol` package owns endpoint templates, protobuf wire
helpers, bundle-source parsing and web-player TOTP handling. Feature modules
keep request payloads and response semantics. `Route` only substitutes and
escapes path segments; it does not implement a second HTTP client or Discord's
rate-limit buckets. Regional hosts remain explicit overrides.

`spotapi.models` is a package of small domain modules. It contains result data
and parsing, without importing account/player clients. Its `catalogue`
subpackage groups catalogue previews and detail contracts. Root client exports
load on access, so importing result models does not load the native transport.
Type-checking imports retain explicit IDE-visible root signatures.

Docstrings explain the operation, ownership and relevant side effects. Type
annotations carry the parameter and return shapes; prose does not repeat them
unless a constraint or protocol detail needs explanation. Overload declarations
share their implementation's documentation.

Resource identity parsing lives in `spotapi.resources`; it has no dependency on
catalogue clients. Shared optional-field coercion lives in the internal
`spotapi._parsing` module, so account parsers do not depend on playback models.
Repeated REST paths and service URLs live in `_protocol.routes`; feature
methods pass path identifiers to `Route.url()` and query parameters to the
HTTP client separately.

Feature helpers borrow the same validated client as `self.http`. Ordinary
requests use `await self.http.get(url, authorized=True)`. The client assembles
credential headers, limits their destination, disables credential-bearing
redirects and applies safe renewal rules. Feature methods specify only headers
that change their representation or payload.

`AsyncClient.transport` exposes unvalidated HTTP responses for protocols such
as account CSRF rotation. `AsyncClient.websocket` exposes the managed socket
transport. Accepted non-success statuses can be declared through
`expected_statuses=(404,)` without bypassing authorization policy.
See [request policy](transport.md) for ownership and replay rules.

Public client and nontrivial method docstrings describe ownership, parameter
constraints, side effects and lazy iteration. Internal docstrings explain a
protocol rule or invariant when it is not evident from the function body;
self-evident representation methods do not need repetitive prose.

`SearchOptions` is a root-exported immutable configuration object. Its Python
fields convert to native GraphQL variables explicitly. `Operations` and
`READ_OPERATIONS` keep built-in names and retry permission together; unknown
operation strings remain an explicit lower-level escape hatch.

The internal `_decoding` module owns model aliases, required-field inspection
and recursive dataclass conversion. Query preflight and actual decoding use
the same rules, including GraphQL's `__typename` metadata field.
