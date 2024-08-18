from __future__ import annotations

import time
from typing import Any, Mapping, Optional, List
from urllib.parse import urlencode, quote

from spotapi.types import Config, SaverProtocol
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

        if self.identifier_credentials is None:
            raise ValueError("Must provide an email or username")

        self.client.fail_exception = LoginError
        self._authorized = False

    def save(self, saver: SaverProtocol) -> None:
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
        password = "" if password is None else password

        cred = dump.get("identifier")
        cookies = dump.get("cookies")

        if isinstance(cookies, str):
            _cookies = cookies.replace(" ", "").split(";")
            cookies = {}
            for cookie in _cookies:
                _k = cookie.split("=")
                k, v = _k[0], _k[1]
                cookies[k] = v

        if isinstance(cookies, Mapping):
            cookies = cookies  # autotype

        if not (cred and cookies):
            raise ValueError(
                "Invalid dump format: must contain 'identifier', and 'cookies'"
            )

        cfg.client.cookies.clear()
        for k, v in cookies.items():
            cfg.client.cookies.set(k, v)

        instantiated = cls(cfg, password, email=cred, username=cred)
        instantiated.logged_in = True

        return instantiated

    @classmethod
    def from_saver(cls, saver: SaverProtocol, cfg: Config, identifier: str) -> Login:
        """
        Loads a session from a Saver Class.
        NOTE: Kwargs are not used, make sure the defaults for the savers are what you want (or just implement this method yourself).
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
    
    def _get_add_cookie(self, _url: str | None = None) -> None:
        urls = ["https://open.spotify.com/", "https://pixel.spotify.com/v2/sync?ce=1&pp="] if not _url else [_url]
        for url in urls:
            resp = self.client.get(url)

            if resp.fail:
                raise LoginError("Could not get session", error=resp.error.string)
    
    def _get_session(self) -> None:
        url = "https://accounts.spotify.com/en/login"
        resp = self.client.get(url)

        if resp.fail:
            raise LoginError("Could not get session", error=resp.error.string)

        self.csrf_token = resp.raw.cookies.get("sp_sso_csrf_token")
        self.flow_id = parse_json_string(resp.response, "flowCtx")
        # Some additional cookies
        self.client.cookies.set("remember", quote(self.identifier_credentials)) # type: ignore
        self._get_add_cookie()

    def _password_payload(self, captcha_key: str) -> str:
        query = {
            "username": self.identifier_credentials,
            "password": self.password,
            "remember": "true",
            "recaptchaToken": captcha_key,
            "continue": "https://accounts.spotify.com/en/status",
            "flowCtx": self.flow_id,
        }

        return urlencode(query)

    def _submit_password(self, token: str) -> None:
        payload = self._password_payload(token)
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
        self._get_add_cookie(f"https://open.spotify.com/?flow_ctx={self.flow_id}")

    def handle_login_error(self, json_data: Mapping[str, Any]) -> None:
        if json_data.get("result") == "ok":
            return

        if json_data.get("result") == "redirect_required":
            self.logger.attempt("Challenge detected, attempting to solve")
            LoginChallenge(self, json_data).defeat()
            self.logger.info("Challenge solved")
            # json_data will still be bad, but we know we are logged in now
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

    def login(self) -> None:
        """Logins the user"""
        if self.logged_in:
            raise LoginError("User already logged in")

        now = time.time()
        self._get_session()

        self.logger.attempt("Solving captcha...")

        if self.solver is None:
            raise LoginError("Solver not set")

        captcha_response = self.solver.solve_captcha(
            "https://accounts.spotify.com/en/login",
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "accounts/login",
            "v3",
        )

        if not captcha_response:
            raise LoginError("Could not solve captcha")

        self.logger.info("Solved Captcha", time_taken=f"{int(time.time() - now)}s")
        self._submit_password(captcha_response)
        self.logger.info(
            "Logged in successfully", time_taken=f"{int(time.time() - now)}s"
        )


class LoginChallenge:
    def __init__(self, login: Login, dump: Mapping[str, Any]) -> None:
        self.l = login
        self.dump = dump

        self.challenge_url = self.dump["data"]["redirect_url"]
        self.interaction_hash: str | None = None
        self.interaction_reference: str | None = None
        self.challenge_session_id: str | None = None

    def _get_challenge(self) -> None:
        resp = self.l.client.get(self.challenge_url)

        if resp.fail:
            raise LoginError("Could not get challenge", error=resp.error.string)

    def _construct_challenge_payload(self) -> Mapping[str, Any]:
        if self.l.solver is None:
            raise LoginError("Solver not set")

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

    def _submit_challenge(self) -> None:
        payload = self._construct_challenge_payload()
        resp = self.l.client.post(**payload)

        if resp.fail:
            raise LoginError("Could not submit challenge", error=resp.error.string)

        if not isinstance(resp.response, Mapping):
            raise LoginError("Invalid JSON")

        self.interaction_hash = resp.response["Completed"]["Hash"]
        self.interaction_reference = resp.response["Completed"]["InteractionReference"]

    def _complete_challenge(self) -> None:
        # We need to grab the cookies
        url = f"https://accounts.spotify.com/login/challenge-completed?sessionId={self.session_id}&interactRef={self.interaction_reference}&hash={self.interaction_hash}"

        resp = self.l.client.get(url)

        if resp.fail:
            raise LoginError("Could not complete challenge", error=resp.error.string)

    def defeat(self) -> None:
        self._get_challenge()
        self._submit_challenge()
        self._complete_challenge()
