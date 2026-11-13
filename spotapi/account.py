"""Account profiles, subscription details and profile updates."""

from __future__ import annotations

import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date
from typing import Any, Self

from ._parsing import mapping, records, string_sequence
from .account_session import AccountSession
from .blend import Blends
from .captcha import CaptchaChallenge, CaptchaSolver, captcha_token
from .client import AsyncClient
from .library import Library, LikedTracks
from .lyrics import LyricsClient
from .models.account import AccountChallenge, AccountPlan, AccountProfile, ProfileValidationError
from .notifications import Notifications
from .profiles import Profiles
from .session import AuthSession
from .stats import ListeningStats
from .transcripts import Transcripts
from .types import BaseClientError, HTTPError

_SITE_KEY = "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39"


class Account:
    """Read account settings and compose authenticated music and social helpers.

    Construction makes no requests. The supplied client or session stays owned
    by the caller; this object never closes it. Use :class:`Private` for a
    managed cookie sign-in scope. Changes are explicit method calls, and batches
    may partially apply before an error is reported.

    Args:
        client: Authorized client or session shared by every helper.
        locale: Account-page locale, such as ``en_US``.
        solver: Optional asynchronous CAPTCHA solver for profile changes.

    Attributes:
        profile: Most recently fetched account settings, or ``None``.
        plan: Most recently fetched subscription card, or ``None``.
        library: Saved resources and artist follows.
        liked_tracks: Track saves and paginated liked songs.
        stats: Spotify affinity rankings.
        profiles: Public profiles and explicit user follows.
        notifications: Notification reads and explicit acknowledgement.
        blends: Blend invitations and explicit joins.
    """

    __slots__ = (
        "session",
        "http",
        "solver",
        "profile",
        "plan",
        "client_nonce",
        "library",
        "liked_tracks",
        "stats",
        "profiles",
        "notifications",
        "blends",
        "transcripts",
        "lyrics",
    )

    def __init__(
        self,
        client: AsyncClient | AuthSession,
        *,
        locale: str = "en_US",
        solver: CaptchaSolver | None = None,
    ) -> None:
        """Borrow an authenticated client; configure locale and an optional CAPTCHA solver."""
        self.session = client.session if isinstance(client, AsyncClient) else client
        self.transcripts = Transcripts(self.session)
        self.lyrics = LyricsClient(self.session)
        self.http = AccountSession(
            self.session.client, "https://www.spotify.com/account/profile/", locale=locale
        )
        self.solver = solver
        self.profile: AccountProfile | None = None
        self.plan: AccountPlan | None = None
        self.client_nonce = str(secrets.randbits(32)) + str(secrets.randbits(32))
        self.library = Library(self.session)
        self.liked_tracks = LikedTracks(self.session)
        self.stats = ListeningStats(self.session)
        self.profiles = Profiles(self.session)
        self.notifications = Notifications(self.session)
        self.blends = Blends(self.session)

    async def get_profile(self) -> AccountProfile:
        """Fetch current account settings and refresh the cached profile."""
        response = await self.http.request("GET", "/api/account-settings/v1/profile", csrf=False)
        self.profile = AccountProfile.from_dict(mapping(response.json))
        return self.profile

    async def get_plan(self) -> AccountPlan:
        """Fetch the account overview subscription card and refresh its CSRF state."""
        page = await self.http.prepare("https://www.spotify.com/account/overview/")
        self.plan = AccountPlan.from_page(page)
        return self.plan

    async def verify_login(self) -> bool:
        """Return false for an expired or refused session; propagate other failures."""
        try:
            await self.get_profile()
        except HTTPError as error:
            if error.status_code in {401, 403}:
                return False
            raise
        return True

    async def validate_profile(self, **fields: str | bool) -> tuple[ProfileValidationError, ...]:
        """Validate only supplied fields without saving profile changes."""
        allowed = {"email", "gender", "birthdate", "country", "third_party_email"}
        if not fields or fields.keys() - allowed:
            raise ValueError("Supply supported profile fields")

        response = await self.http.request(
            "POST", "/api/account-settings/v1/validate", body={"profile": fields}
        )
        body = mapping(response.json)
        if not isinstance(body.get("validation_errors"), list):
            raise BaseClientError("Spotify returned no profile validation result")
        return tuple(
            ProfileValidationError(
                str(row.get("field", "")),
                string_sequence(row.get("errors", ()), "validation errors"),
            )
            for row in records(body["validation_errors"])
        )

    async def edit_profile(
        self,
        *,
        email: str | None = None,
        gender: str | None = None,
        birthdate: date | None = None,
        country: str | None = None,
        third_party_email: bool | None = None,
        password: str | None = None,
        token: str | None = None,
    ) -> AccountProfile | AccountChallenge:
        """Merge supplied changes into freshly fetched account settings.

        Args:
            email: New email address, if editable for this account.
            gender: Value from the profile's ``available_genders``.
            birthdate: New calendar birthdate.
            country: Code from the profile's ``available_countries``.
            third_party_email: Value for Spotify's third-party-email preference.
            password: Current password when Spotify requires it for an email change.
            token: Fresh CAPTCHA response; an injected solver is used if omitted.

        Returns:
            Updated settings, or a browser challenge that the caller must complete.
            Returning a challenge does not mean the requested changes were saved.

        Raises:
            ValueError: No changes were supplied, a field is not editable, an
                option is invalid, or a required password or CAPTCHA token is empty.
            CaptchaRequired: No CAPTCHA token or solver was supplied.
            BaseClientError: Spotify returned invalid account settings.
            HTTPError: Spotify rejected the request.

        Note:
            Omitted fields remain unchanged. The mutation is sent once; after an
            ambiguous failure, read the current profile before deciding to retry.
        """
        changes = {
            key: value
            for key, value in {
                "email": email,
                "gender": gender,
                "birthdate": birthdate.isoformat() if birthdate is not None else None,
                "country": country,
                "third_party_email": third_party_email,
            }.items()
            if value is not None
        }
        if not changes:
            raise ValueError("Supply at least one profile field to change")

        profile = await self.get_profile()
        if profile.editable_fields and changes.keys() - set(profile.editable_fields):
            raise ValueError("Spotify does not allow editing one or more requested fields")
        if country is not None and country not in profile.available_countries:
            raise ValueError("Choose an available country code from the profile")
        if gender is not None and gender not in profile.available_genders:
            raise ValueError("Choose an available gender from the profile")
        if email is not None and profile.password_required_for_email_change and not password:
            raise ValueError("Spotify requires the current password to change this email")

        challenge = CaptchaChallenge(
            "https://www.spotify.com", _SITE_KEY, "account_settings/profile_update"
        )
        solved = await captcha_token(challenge, token, self.solver)
        values: dict[str, Any] = {
            "email": profile.email,
            "gender": profile.gender,
            "birthdate": profile.birthdate.isoformat() if profile.birthdate else None,
            "country": profile.country,
            "third_party_email": profile.third_party_email,
            **changes,
        }
        body: dict[str, Any] = {
            "profile": values,
            "recaptcha_token": solved,
            "client_nonce": self.client_nonce,
            "callback_url": "https://www.spotify.com/account/profile/challenge",
            "client_info": {"locale": self.http.locale, "capabilities": [1]},
        }
        if password is not None:
            body["password"] = password

        response = await self.http.request("PUT", "/api/account-settings/v2/profile", body=body)
        result = mapping(response.json)
        if "challenge_response" in result:
            data = mapping(result["challenge_response"])
            return AccountChallenge(
                str(data["challenge_url"]), str(data["session_id"]), str(data["server_nonce"])
            )

        self.profile = AccountProfile.from_dict(
            mapping(result.get("user_profile_response", result))
        )
        return self.profile

    async def logout_everywhere(self) -> None:
        """Revoke Spotify sessions everywhere and stop this session's token refresh."""
        await self.session.client.get(
            "https://accounts.spotify.com/revoke_sessions/",
            query={"continue": "https://www.spotify.com"},
            max_attempts=1,
        )
        await self.session.stop_refresh()

    async def change_password(self, current_password: str, new_password: str) -> None:
        """Change the account password using its current password; send once."""
        if not current_password or not new_password:
            raise ValueError("Current and new passwords are required")
        await self.http.request(
            "PUT",
            "/api/account-settings/v1/change-password",
            body={"old_password": current_password, "new_password": new_password},
        )

    async def set_password(self, new_password: str) -> None:
        """Set the first password for an account created through another provider."""
        if not new_password:
            raise ValueError("A new password is required")
        await self.http.request(
            "PUT", "/api/account-settings/v1/set-password", body={"new_password": new_password}
        )


class Private(Account):
    """Use account operations inside a managed cookie-authenticated scope.

    Enter ``Private.from_cookies(cookie)`` with ``async with``. It authorizes
    the session and closes its transports and token refresh task on exit.
    Inherited account helpers all share that session.
    """

    __slots__ = ()

    @classmethod
    @asynccontextmanager
    async def from_cookies(
        cls, cookies: str, *, proxy: str | None = None, language: str = "en"
    ) -> AsyncGenerator[Self]:
        """Open an account with explicit connection options and close it on exit."""
        async with await AsyncClient.from_cookies(
            cookies, proxy=proxy, language=language
        ) as client:
            yield cls(client)
