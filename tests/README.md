# Tests

`python -m pytest -q` runs offline tests and skips live tests by default.
`python -m pyright` checks the library, examples and tests in strict mode.

Use `python -m pytest --live=read -vv` for all live reads. This single switch
covers public catalogue reads and authenticated checks when `SPOTIFY_COOKIE`
is available in the environment or root `.env`. Missing credentials skip only
authenticated checks. `python -m pytest --live=all -vv` also permits
playback changes. No environment feature flags are required.

Tests permit access to private members for lifecycle assertions; other strict
diagnostics remain enabled.

Transport and lifecycle tests use deterministic fakes; catalogue integration
tests check actual Spotify response shapes separately. The shared-client
tests verify creation, concurrent borrowing, cancellation, and shutdown.
