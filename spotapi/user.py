from __future__ import annotations

from typing import Any, Mapping

from spotapi.exceptions import UserError
from spotapi.login import Login

import secrets

class User:
    """
    Represents a Spotify user.
    """

    def __init__(self, login: Login) -> None:
        if not login.logged_in:
            raise ValueError("Must be logged in")

        self.login = login
        self._user_plan: Mapping[str, Any] | None = None
        self._user_info: Mapping[str, Any] | None = None

    @property
    def has_premium(self) -> bool:
        if self._user_plan is None:
            self._user_plan = self.get_plan_info()

        return self._user_plan["plan"]["name"] != "Spotify Free"

    @property
    def username(self) -> str:
        if self._user_info is None:
            self._user_info = self.get_user_info()

        return self._user_info["profile"]["username"]

    def get_plan_info(self) -> Mapping[str, Any]:
        """Gets user plan info."""
        url = "https://www.spotify.com/ca-en/api/account/v2/plan/"
        resp = self.login.client.get(url)

        if resp.fail:
            raise UserError("Could not get user plan info", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise UserError("Invalid JSON")

        return resp.response

    def verify_login(self) -> bool:
        try:
            self.get_plan_info()
        except Exception as e:
            if "401" in str(e):
                return False
            raise e
        else:
            return True

    def get_user_info(self) -> Mapping[str, Any]:
        """Gets accounts user info."""
        url = "https://www.spotify.com/api/account-settings/v1/profile"
        resp = self.login.client.get(url)

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
        if self.login.solver is None:
            raise UserError("Captcha solver not set")

        captcha_response = self.login.solver.solve_captcha(
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
            "client_nonce": ''.join(str(secrets.randbits(32)) for _ in range(2)),
            "callback_url": "https://www.spotify.com/account/profile/challenge",
            "client_info": {
                "locale": "en_US",
                "capabilities": [
                    1
                ]
            }
        }

        url = "https://www.spotify.com/api/account-settings/v2/profile"

        headers = {
            "Content-Type": "application/json",
            "X-Csrf-Token": self.csrf_token,
        }

        resp = self.login.client.put(url, json=dump, headers=headers)

        if resp.fail:
            raise UserError("Could not edit  user info", error=resp.error.string)
