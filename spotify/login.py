from __future__ import annotations
from spotify.data import Config
from typing import Optional, Any, List, Type
from spotify.utils.strings import parse_json_string
from spotify.exceptions import LoginError
from spotify.interfaces import SaverProtocol
from urllib.parse import urlencode
from http.cookiejar import Cookie


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

    @classmethod
    def from_cookies(cls, dump: dict[str, Any], cfg: Config) -> Login:
        """
        Constructs a Login instance using cookie data and configuration.
        """
        password = dump.get("password")
        cred = dump.get("identifier")
        cookies: List[dict[str, Any]] = dump.get("cookies")

        if not (password and cred and cookies):
            raise ValueError("Invalid dump format: must contain 'password', 'identifier', and 'cookies'")

        cfg.client.cookies.clear()
        for cookie in cookies:
            cfg.client.cookies.set(**cookie)

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

    def __submit_password(self) -> None:
        captcha_response = self.solver.solve_captcha(
            "https://accounts.spotify.com/en/login",
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "accounts/login",
            "v3",
        )

        if not captcha_response:
            raise LoginError("Could not solve captcha")

        payload = self.__password_payload(captcha_response)
        url = "https://accounts.spotify.com/login/password"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "X-CSRF-Token": self.csrf_token,
        }

        resp = self.client.post(url, data=payload, headers=headers)

        if resp.fail:
            raise LoginError("Could not submit password", error=resp.error.string)

        self.csrf_token = resp.raw.cookies.get("sp_sso_csrf_token")
        self.handle_login_error(resp.response)
        self.logged_in = True

    def handle_login_error(self, json_data: dict) -> None:
        if json_data.get("result") == "ok":
            return

        if "error" not in json_data:
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

    def verify_login(self) -> None:
        """Verifies if the user is logged in (useful for checking if cookies are still valid)"""

    def login(self) -> None:
        """Logins the user"""
        self.__get_session()
        self.__submit_password()
