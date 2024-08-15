from __future__ import annotations

import time
from typing import Any, Mapping, Optional, Type
from urllib.parse import urlencode

from spotapi.data import Config, SaverProtocol
from spotapi.exceptions import LoginError
from spotapi.utils.strings import parse_json_string


class Login:
    """
    Base class for logging in to Spotify.
    """

    def __init__(
        self,
        cfg: Config,
        password: str,
        *,
        email: Optional[str] = None,
        username: Optional[str] = None,
    ):
        self.solver = cfg.solver
        self.client = cfg.client
        self.logger = cfg.logger

        self.password = password
        self.identifier_credentials = username or email

        if not self.identifier_credentials:
            raise ValueError("Must provide an email or username")

        if not self.solver:
            raise ValueError("Must provide a Captcha solver")

        self.client.fail_exception = LoginError
        self._authorized = False

    def save(self, saver: Type[SaverProtocol]) -> None:
        """
        Saves the session with the provided Saver.
        """
        if not self.logged_in:
            raise ValueError("Cannot save session if it is not logged in")

        saver.save(
            [
                {
                    "identifier": self.identifier_credentials,
                    "password": self.password,
                    "cookies": self.client.cookies.get_dict(),
                }
            ]
        )

    @classmethod
    def from_cookies(cls, dump: Mapping[str, Any], cfg: Config) -> Login:
        """
        Constructs a Login instance using cookie data and configuration.
        """
        password = dump.get("password")
        cred = dump.get("identifier")
        cookies: Mapping[str, Any] = dump.get("cookies")

        if not (password and cred and cookies):
            raise ValueError(
                "Invalid dump format: must contain 'password', 'identifier', and 'cookies'"
            )

        cfg.client.cookies.clear()
        for k, v in cookies.items():
            cfg.client.cookies.set(k, v)

        instantiated = cls(cfg, password, email=cred, username=cred)
        instantiated.logged_in = True

        return instantiated

    @classmethod
    def from_saver(
        cls, saver: Type[SaverProtocol], cfg: Config, identifier: str
    ) -> Login:
        """
        Loads a session from a Saver Class.

        Note: Kwargs are not used, make sure the defaults for the savers are what you want (or just implement this method yourself).
        """
        dump = saver.load(query={"identifier": identifier})
        return cls.from_cookies(dump, cfg)

    @property
    def logged_in(self) -> bool:
        return self._authorized

    @logged_in.setter
    def logged_in(self, value: bool):
        self._authorized = value

    def __str__(self) -> str:
        return f"Login(password={self.password!r}, identifier_credentials={self.identifier_credentials!r})"

    def __get_session(self) -> None:
        url = "https://accounts.spotify.com/en/login"
        resp = self.client.get(url)

        if resp.fail:
            raise LoginError("Could not get session", error=resp.error.string)

        self.csrf_token = resp.raw.cookies.get("sp_sso_csrf_token")
        self.flow_id = parse_json_string(resp.response, "flowCtx")

    def __password_payload(self, captcha_key: str) -> str:
        query = {
            "username": self.identifier_credentials,
            "password": self.password,
            "remember": "true",
            "recaptchaToken": captcha_key,
            "continue": "https://accounts.spotify.com/en/status",
            "flowCtx": self.flow_id,
        }

        return urlencode(query)

    def __submit_password(self, token: str) -> None:
        payload = self.__password_payload(token)
        url = "https://accounts.spotify.com/login/password"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Csrf-Token": self.csrf_token,
        }

        resp = self.client.post(url, data=payload, headers=headers)

        if resp.fail:
            raise LoginError("Could not submit password", error=resp.error.string)

        self.csrf_token = resp.raw.cookies.get("sp_sso_csrf_token")
        self.handle_login_error(resp.response)
        self.logged_in = True

    def handle_login_error(self, json_data: Mapping[str, Any]) -> None:
        if json_data.get("result") == "ok":
            return

        if json_data.get("result") == "redirect_required":
            self.logger.attempt("Challenge detected, attempting to solve")
            LoginChallenge(self, json_data).defeat()
            self.logger.info("Challenge solved")
            # json_data will still be bad, but we know we are logged in now
            return

        if not ("error" in json_data):
            raise LoginError(f"Unexpected response format: {json_data}")

        error_type = json_data["error"]

        match (error_type):
            case "errorUnknown":
                raise LoginError("ErrorUnknown, Needs retrying")
            case "errorInvalidCredentials":
                raise LoginError(
                    "Invalid Credentials", error=f"{str(self)}: {error_type}"
                )
            case _:
                raise LoginError(f"Unforseen Error", error=f"{str(self)}: {error_type}")

    def login(self) -> None:
        """Logins the user"""
        now = time.time()
        self.__get_session()

        self.logger.attempt("Solving captcha...")
        captcha_response = self.solver.solve_captcha(
            "https://accounts.spotify.com/en/login",
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "accounts/login",
            "v3",
        )

        if not captcha_response:
            raise LoginError("Could not solve captcha")

        self.logger.info("Solved Captcha", time_taken=f"{int(time.time() - now)}s")
        self.__submit_password(captcha_response)
        self.logger.info(
            "Logged in successfully", time_taken=f"{int(time.time() - now)}s"
        )


class LoginChallenge:
    def __init__(self, login: Login, dump: Mapping[str, Any]) -> None:
        self.l = login
        self.dump = dump

        self.challenge_url = self.dump["data"]["redirect_url"]
        self.interaction_hash: str = None
        self.interaction_reference: str = None
        self.challenge_session_id: str = None

    def __get_challenge(self) -> None:
        resp = self.l.client.get(self.challenge_url)

        if resp.fail:
            raise LoginError("Could not get challenge", error=resp.error.string)

    def __construct_challenge_payload(self) -> Mapping[str, Any]:
        captcha_response = self.l.solver.solve_captcha(
            self.challenge_url,
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "accounts/login",
            "v3",
        )

        if not captcha_response:
            raise LoginError("Could not solve captcha")

        self.session_id = self.challenge_url.split("c/")[1].split("/")[0]
        challenge_id = self.challenge_url.split(self.session_id + "/")[1].split("/")[0]

        uri = "https://challenge.spotify.com/api/v1/invoke-challenge-command"
        payload = {
            "session_id": self.session_id,
            "challenge_id": challenge_id,
            "recaptcha_challenge_id": {"solve": {"recaptcha_token": captcha_response}},
        }
        headers = {
            "X-Cloud-Trace-Context": "00000000000000006979d1624aa6b213/2238380859227873585;o=1",
            "Content-Type": "application/json",
        }

        return {"url": uri, "json": payload, "headers": headers}

    def __submit_challenge(self) -> None:
        payload = self.__construct_challenge_payload()
        resp = self.l.client.post(**payload)

        if resp.fail:
            raise LoginError("Could not submit challenge", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise LoginError("Invalid JSON")

        self.interaction_hash = resp.response["Completed"]["Hash"]
        self.interaction_reference = resp.response["Completed"]["InteractionReference"]

    def __complete_challenge(self) -> None:
        # We need to grab the cookies
        url = f"https://accounts.spotify.com/login/challenge-completed?sessionId={self.session_id}&interactRef={self.interaction_reference}&hash={self.interaction_hash}"

        resp = self.l.client.get(url)

        if resp.fail:
            raise LoginError("Could not complete challenge", error=resp.error.string)

    def defeat(self) -> None:
        self.__get_challenge()
        self.__submit_challenge()
        self.__complete_challenge()
