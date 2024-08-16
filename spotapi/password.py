from spotapi.utils.strings import parse_json_string
from spotapi.exceptions import PasswordError
from spotapi.types.data import Config
from typing import Optional
import time
import uuid


class Password:
    """
    Preforms password recoveries.
    """

    def __init__(
        self,
        cfg: Config,
        *,
        email: Optional[str] = None,
        username: Optional[str] = None,
    ):
        self.solver = cfg.solver
        self.client = cfg.client
        self.logger = cfg.logger

        self.identifier_credentials = username or email

        if not self.identifier_credentials:
            raise ValueError("Must provide an email or username")

    def __get_session(self) -> None:
        url = "https://accounts.spotify.com/en/password-reset"
        resp = self.client.get(url)

        if resp.fail:
            raise PasswordError("Could not get session", error=resp.error.string)

        self.csrf = parse_json_string(resp.response, "csrf")
        self.flowID = str(uuid.uuid4())

    def __reset_password(self, token: str) -> None:
        payload = {
            "captcha": token,
            "emailOrUsername": self.identifier_credentials,
            "flowId": self.flowID,
        }
        url = "https://accounts.spotify.com/api/password/recovery"
        headers = {
            "X-Csrf-Token": self.csrf,
        }

        resp = self.client.post(url, data=payload, headers=headers)

        if resp.fail:
            raise PasswordError("Could not reset password", error=resp.error.string)

    def reset(self) -> None:
        self.__get_session()

        now = time.time()
        self.logger.attempt("Solving captcha...")

        captcha_response = self.solver.solve_captcha(
            "https://accounts.spotify.com/en/password-reset",
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "password_reset_web/recovery",
            "v3",
        )

        if not captcha_response:
            raise PasswordError("Could not solve captcha")

        self.logger.info("Solved Captcha", time_taken=f"{int(time.time() - now)}s")
        self.__reset_password(captcha_response)
        self.logger.info(
            "Successfully reset password", time_taken=f"{int(time.time() - now)}s"
        )
