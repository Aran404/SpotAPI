from spotapi.utils.strings import parse_json_string
from spotapi.exceptions import PasswordError
from spotapi.types.data import Config
from spotapi.types.annotations import enforce
import time
import uuid

__all__ = ["Password", "PasswordError"]


@enforce
class Password:
    """
    Preforms password recoveries.

    Parameters
    ----------
    cfg (Config): Configuration object.
    email (Optional[str], optional): Email address to use for recovery. Defaults to None.
    username (Optional[str], optional): Username to use for recovery. Defaults to None.

    Email or username must be provided.
    """

    __slots__ = (
        "solver",
        "client",
        "logger",
        "identifier_credentials",
        "csrf",
        "flowID",
    )

    def __init__(
        self,
        cfg: Config,
        *,
        email: str | None = None,
        username: str | None = None,
    ) -> None:
        self.solver = cfg.solver
        self.client = cfg.client
        self.logger = cfg.logger

        self.identifier_credentials = username or email

        if not self.identifier_credentials:
            raise ValueError("Must provide an email or username")

    def _get_session(self) -> None:
        url = "https://accounts.spotify.com/en/password-reset"
        resp = self.client.get(url)

        if resp.fail:
            raise PasswordError("Could not get session", error=resp.error.string)

        self.csrf = parse_json_string(resp.response, "csrf")
        self.flowID = str(uuid.uuid4())

    def _reset_password(self, token: str) -> None:
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
        self._get_session()
        now = time.time()
        self.logger.attempt("Solving captcha...")

        if self.solver is None:
            raise PasswordError("Solver not set")

        captcha_response = self.solver.solve_captcha(
            "https://accounts.spotify.com/en/password-reset",
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "password_reset_web/recovery",
            "v3",
        )

        if not captcha_response:
            raise PasswordError("Could not solve captcha")

        self.logger.info("Solved Captcha", time_taken=f"{int(time.time() - now)}s")
        self._reset_password(captcha_response)
        self.logger.info(
            "Successfully reset password", time_taken=f"{int(time.time() - now)}s"
        )
