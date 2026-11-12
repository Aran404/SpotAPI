"""Account settings, subscription cards and explicit edit challenges."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import TYPE_CHECKING, Any

from spotapi._parsing import mapping, records, string_sequence
from spotapi.types import BaseClientError

if TYPE_CHECKING:
    from spotapi.account_session import AccountPage


@dataclass(frozen=True, slots=True)
class ProfileValidationError:
    """Validation messages for one profile field; no changes have been saved."""

    field: str
    errors: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class AccountProfile:
    """Current account settings and server-provided editing choices.

    Use ``editable_fields``, ``available_countries`` and ``available_genders``
    when preparing an edit. Email and birthdate are excluded from repr. Reading
    this model does not refresh settings or change the account.
    """

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
            editable_fields=string_sequence(options.get("editable_fields", ()), "editable_fields"),
            available_countries=string_sequence(
                options.get("available_countries", ()), "available_countries"
            ),
            available_genders=string_sequence(
                options.get("available_genders", ()), "available_genders"
            ),
            password_required_for_email_change=options.get("is_password_required_on_email_change")
            is True,
        )


@dataclass(frozen=True, slots=True)
class AccountPlan:
    """The subscription card displayed on the account overview page.

    ``is_premium`` is inferred from the displayed plan name. It is None when
    the localized name cannot be classified; it is not an entitlement check.
    """

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
    """A browser challenge returned instead of a completed profile update.

    Open ``url`` through your own browser flow. The opaque session ID and nonce
    are excluded from repr and do not prove that the change was saved.
    """

    url: str
    session_id: str = field(repr=False)
    server_nonce: str = field(repr=False)
