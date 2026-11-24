# Your Spotify, in Python

Account helpers borrow the client you give them. One context closes authentication,
refresh tasks and HTTP connections for the whole application.

Mutations validate Spotify's returned confirmation and are not replayed after
ambiguous failures. A batch can partially apply before an error is reported;
read the resulting saved, pinned or followed state before retrying.

```python
import asyncio
import os

from spotapi import Private


async def show_favorites() -> None:
    async with Private.from_cookies(os.environ["SPOTIFY_COOKIE"]) as account:
        favorites = await account.stats.get(time_range="medium_term", limit=5)
        for track in favorites.tracks:
            print(track.name, track.uri)


asyncio.run(show_favorites())
```

`Private.from_cookies` also accepts `proxy` and `language` keyword arguments.

Catch `LoginExpired` to ask the user for a fresh Spotify session:

```python
from spotapi import AsyncClient, LoginExpired

try:
    client = await AsyncClient.from_cookies(cookie)
except LoginExpired:
    print("Log in to Spotify again and update your sp_dc cookie.")
else:
    async with client:
        # Use account helpers here.
        pass
```

The exception covers a missing `sp_dc`, a 401 during login bootstrap or token
issuance, and a cookie session downgraded to anonymous access. It subclasses `HTTPError`
and retains its status and cause when present. Other HTTP failures, including
400/403 responses that do not establish a rejected login, retain their
original exception.

`ListeningStats`, `Library`, `LikedTracks`, `Profiles`, `Notifications` and `Blends`
also work independently with the same client. Helpers never close a borrowed client.
Use `Catalogue(client)` for authenticated catalogue reads, including private playlists.

| Want to… | Call |
|---|---|
| Read account settings | `await account.get_profile()` |
| Read the subscription card | `await account.get_plan()` |
| Get top artists and tracks together | `await account.stats.get()` |
| Stream saved tracks | `async for page in account.liked_tracks.pages(): ...` |
| Like or unlike tracks | `await account.liked_tracks.add([track])` / `await account.liked_tracks.remove([track])` |
| Check whether a track is liked | `await account.liked_tracks.contains([track])` |
| Follow or unfollow an artist | `await account.library.follow_artists(artist)` / `await account.library.unfollow_artists(artist)` |
| Check artist follows | `await account.library.is_following_artists(artist)` |
| Stream the library | `async for item in account.library.items(): ...` |
| Inspect available library filters | `(await account.library.get()).filters` |
| Read notifications | `await account.notifications.get()` |
| Check the notification badge | `await account.notifications.has_unread()` |
| Acknowledge an opened page | `await account.notifications.mark_seen(page.latest_cursor)` |
| Make a Blend invitation | `await account.blends.create()` |
| Join an invitation | `await account.blends.join(invitation_url)` |

Affinity ranges are `short_term`, `medium_term` and `long_term`. These are Spotify's
rankings, not a complete listening history or a replacement for Wrapped. Library
filter IDs and sort orders come from the returned page; do not invent category IDs.
Follower lists are server previews capped at 1,000, not complete paginated exports.
Artist follows use Your Library. Use `account.profiles.follow()` for Spotify
user profiles. Liked-track add/remove and artist follow lookups have live
coverage. Artist follow and unfollow writes have offline contract coverage.

## Profile changes and CAPTCHA

`edit_profile` fetches the current profile before merging explicitly supplied
changes. It checks editable fields and allowed values, preserves unrelated settings,
and returns either the updated `AccountProfile` or an `AccountChallenge` for a
required browser challenge. Challenge completion is not automated.

Pass `token=` with a freshly obtained CAPTCHA token, or supply your own solver:

```python
from spotapi import CaptchaChallenge


class MySolver:
    async def solve(self, challenge: CaptchaChallenge) -> str:
        return await my_captcha_service.solve(
            website_url=challenge.website_url,
            site_key=challenge.site_key,
            action=challenge.action,
        )
```

`my_captcha_service` is your application integration. SpotAPI's `CaptchaSolver`
protocol has no vendor dependency. Without a token or solver, `CaptchaRequired`
includes the challenge details. Password recovery uses the same protocol through
`PasswordReset(client)`. Password changes, recovery emails and logout everywhere
are explicit operations; constructing an account never triggers them.

<!-- CapSolver: 30-day trial from publication; remove unless renewed. -->

**Maintainer's note (sponsored):** I've personally used CapSolver for several years, and it's one option I'd consider for authorized CAPTCHA workflows. [CapSolver](https://dashboard.capsolver.com/passport/register?inviteCode=2aMq4nxxiQJX){ rel="sponsored nofollow" } provides account credits for this placement, and I may earn a referral commission. It is entirely optional; SpotAPI remains provider-neutral and does not guarantee compatibility.

Subscription data comes from Spotify's account overview page because the old v1
plan route no longer works. `is_premium` is inferred from the displayed plan name
and can be `None` for an unrecognized localized name.

## Verification boundaries

Account/profile/plan reads, all affinity ranges, saved tracks, library pagination,
notification reads, and matching JSON/protobuf profile fields were checked live on
2026-11-10. A Blend invitation was generated successfully. Profile/password edits,
session revocation, follower mutations, Blend joining and notification acknowledgement
have request-contract tests or source verification, not successful live mutation
coverage. They are not claimed as end-to-end verified.
