"""Account profiles, subscription details and profile updates."""

from __future__ import annotations

import secrets
from collections.abc import AsyncGenerator, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Self

from .account_session import AccountPage, AccountSession
from .blend import Blends
from .captcha import CaptchaChallenge, CaptchaSolver, captcha_token
from .client import AsyncClient
from .library import Library, LikedTracks
from .notifications import Notifications
from .playback import mapping, records
from .profiles import Profiles
from .session import AuthSession
from .stats import ListeningStats
from .types import BaseClientError, HTTPError

_SITE_KEY = "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39"


@dataclass(frozen=True, slots=True)
class ProfileValidationError:
    field: str
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccountProfile:
    username: str
    email: str = field(repr=False)
    gender: str
    birthdate: date | None = field(repr=False)
    country: str
    third_party_email: bool = False
    editable_fields: tuple[str, ...] = ()
    available_countries: tuple[str, ...] = ()
    available_genders: tuple[str, ...] = ()
    password_required_for_email_change: bool = False

    @classmethod
    def from_dict(cls, body: Mapping[str, Any]) -> AccountProfile:
        """Parse profile settings and editable options; redact personal fields from repr."""
        value = mapping(body.get("profile"))
        options = mapping(body.get("options"))
        if not isinstance(value.get("username"), str) or not isinstance(value.get("email"), str):
            raise BaseClientError("Spotify returned no account profile")

        birthday = value.get("birthdate")
        try:
            birthdate = date.fromisoformat(birthday) if birthday else None
        except (ValueError, TypeError) as error:
            raise BaseClientError("Spotify returned an invalid birthdate") from error

        return cls(
            username=value["username"],
            email=value["email"],
            gender=str(value.get("gender", "")),
            birthdate=birthdate,
            country=str(value.get("country", "")),
            third_party_email=value.get("third_party_email") is True,
            editable_fields=tuple(options.get("editable_fields", ())),
            available_countries=tuple(options.get("available_countries", ())),
            available_genders=tuple(options.get("available_genders", ())),
            password_required_for_email_change=options.get("is_password_required_on_email_change")
            is True,
        )


@dataclass(frozen=True, slots=True)
class AccountPlan:
    name: str
    description: str
    sub_description: str
    is_premium: bool | None

    @classmethod
    def from_page(cls, page: AccountPage) -> AccountPlan:
        """Read the subscription card from the current account overview page."""
        props = mapping(mapping(page.data.get("props")).get("pageProps"))
        widgets = mapping(props.get("dynamicWidgets"))
        plans = records(widgets.get("PlanCard"))
        plan = mapping(plans[0].get("props")) if plans else mapping(None)
        name = plan.get("planName")
        if not isinstance(name, str) or not name:
            raise BaseClientError("Spotify returned no subscription plan card")

        lowered = name.casefold()
        premium = True if "premium" in lowered else False if "free" in lowered else None
        return cls(
            name,
            str(plan.get("description", "")),
            str(plan.get("subDescription", "")),
            premium,
        )


@dataclass(frozen=True, slots=True)
class AccountChallenge:
    url: str
    session_id: str = field(repr=False)
    server_nonce: str = field(repr=False)


class Account:
    """Use ``await Account(client).get_profile()`` with an authenticated client."""

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
            ProfileValidationError(str(row.get("field", "")), tuple(row.get("errors", ())))
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
        """Merge supplied changes into a fresh profile; return a profile or browser challenge.

        Supply a fresh CAPTCHA token or configure a solver. Omitted fields remain unchanged."""
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
    """Authenticated account operations with a managed cookie sign-in shortcut."""

    __slots__ = ()

    @classmethod
    @asynccontextmanager
    async def from_cookies(cls, cookies: str) -> AsyncGenerator[Self]:
        """Open an authenticated account and close its client on context exit."""
        async with await AsyncClient.from_cookies(cookies) as client:
            yield cls(client)
