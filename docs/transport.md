# Requests and authorization

Use account, catalogue and player helpers for supported operations. When adding
an endpoint, borrow their existing client and declare the request's intent:

```python
response = await self.http.get(
    LYRICS.url(base=endpoints.spclient, track=track_id),
    authorized=True,
    query={"format": "json", "market": "from_token"},
)
```

This is an internal feature example: `LYRICS` is imported from
`spotapi._protocol.routes`. Route parameters are raw identifiers; the template
encodes them once as individual path segments. Query parameters stay separate.
Feature modules own payloads and response parsing, while the route bank owns
repeated paths and service locations.

For an application integration, open a managed client:

```python
client = await AsyncClient.from_cookies(cookie)
try:
    response = await client.get(spotify_endpoint, authorized=True)
finally:
    await client.close()
```

Import `AsyncClient` from `spotapi`. `cookie` and `spotify_endpoint` are supplied
by the application. Never log the cookie or generated credential headers.

## Ownership

`AsyncClient` owns its transports and stops its attached session's refresh task
when closing. `AuthSession(client)` attaches to an already open client; another
session cannot replace it. Its `close()` closes that client too. Feature helpers
borrow this scope and do not create independent connections or refresh tasks.

`self.http` on a feature helper is the validated `AsyncClient`. The lower-level
`client.transport` returns responses without status validation and does not
provide managed authorization. It exists for protocols that explicitly handle
CSRF rotation, cookies or their own authentication flow.

## Credential policy

`authorized=True` requires a prepared authentication session. It assembles the
current bearer token, client token and web-player headers centrally. Only HTTPS
Spotify hosts are accepted. Redirects are disabled, including same-host redirects,
so custom credential headers cannot be forwarded to another origin. A redirect
therefore raises unless its status was explicitly expected.

Supply representation headers such as `accept` normally. Authorized requests
require string-to-string header mappings, normalize names case-insensitively and
reject attempts to replace `authorization` or `client-token`. The caller's
mapping is copied. Anonymous bootstrap and cookie/CSRF requests do not opt into
this bearer-token policy.

## Replay and status handling

| Option | Meaning |
|---|---|
| `retry_safe=None` | GET, HEAD, OPTIONS and TRACE are replay-safe by method |
| `retry_safe=True` | Explicitly permit replay for a known read-only operation, including a POST |
| `retry_safe=False` | Disable method-based replay permission |
| `max_attempts=1` | One transport attempt and no automatic 401 renewal replay |
| `max_attempts=N` | Explicit transport-attempt budget, including the first; values above one permit transport replay even for a mutation |
| `expected_statuses=(404,)` | Return this additional status for endpoint-specific handling |

After an unexpected 401, a replay-safe authorized request may renew credentials
and make one further transport attempt. Concurrent renewal is coordinated by
the session. That replay uses fresh credential headers and is not renewed again.
A renewal replay is separate from the initial transport-attempt budget, except
that `max_attempts=1` disables it entirely. Expected 401 responses do not renew.

Mutations make one attempt. A timeout does not prove the server rejected a
change; reconcile current state before retrying. Built-in Pathfinder reads use
an explicit allowlist. Unknown operations do not inherit read permissions.

Successful JSON responses must contain a JSON object. HEAD responses and 204/205
statuses may be empty. An explicitly expected *successful* status still undergoes
body validation; an expected non-success status is returned for the caller to
interpret. `Response.json` does not represent JSON arrays or scalar values.
