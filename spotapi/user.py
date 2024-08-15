from __future__ import annotations

from typing import Any, Mapping

from spotapi.exceptions import UserError
from spotapi.login import Login


class User(Login):
    """
    Represents a Spotify user.
    """

    def __new__(cls, login: Login) -> User:
        instance = super(User, cls).__new__(cls)
        instance.__dict__.update(login.__dict__)
        return instance

    def __init__(self, login: Login) -> None:
        if not login.logged_in:
            raise ValueError("Must be logged in")

        self._user_plan: Mapping[str, Any] = None
        self._user_info: Mapping[str, Any] = None

    @property
    def has_premium(self) -> bool:
        if self._user_plan is None:
            self.get_plan_info()

        return self._user_plan["plan"]["name"] != "Spotify Free"

    @property
    def username(self) -> str:
        if self._user_info is None:
            self._user_info = self.get_user_info()

        return self._user_info["profile"]["username"]

    def get_plan_info(self) -> Mapping[str, Any]:
        """Gets user plan info."""
        url = "https://www.spotify.com/ca-en/api/account/v2/plan/"
        resp = self.client.get(url)

        if resp.fail:
            raise UserError("Could not get user plan info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise UserError("Invalid JSON")

        self._user_plan = resp.response
        return resp.response

    def verify_login(self) -> bool:
        try:
            self.get_plan_info()
        except Exception as e:
            if "401" in str(e):
                return False
        else:
            return True

    def get_user_info(self) -> Mapping[str, Any]:
        """Gets accounts user info."""
        url = "https://www.spotify.com/api/account-settings/v1/profile"
        resp = self.client.get(url)

        if resp.fail:
            raise UserError("Could not get user info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise UserError("Invalid JSON")

        self.csrf_token = resp.raw.headers.get("X-Csrf-Token")
        return resp.response

    def edit_user_info(self, dump: Mapping[str, Any]) -> None:
        """
        Edits account user account info.
        For this function to work, dump must be the entire profile dump.
        You can get this dump from get_user_info, then change the fields you want.
        """
        captcha_response = self.solver.solve_captcha(
            "https://www.spotify.com",
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "account_settings/profile_update",
            "v3",
        )

        if not captcha_response:
            raise UserError("Could not solve captcha")

        profile_dump = dump["profile"]
        dump = {
            "profile": {
                "email": profile_dump["email"],
                "gender": profile_dump["gender"],
                "birthdate": profile_dump["birthdate"],
                "country": profile_dump["country"],
            },
            "recaptcha_token": captcha_response,
        }

        url = "https://www.spotify.com/api/account-settings/v1/profile"

        headers = {
            "Content-Type": "application/json",
            "X-Csrf-Token": self.csrf_token,
        }

        resp = self.client.put(url, json=dump, headers=headers)

        if resp.fail:
            raise UserError("Could not edit user info", error=resp.error.string)