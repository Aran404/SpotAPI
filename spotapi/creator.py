import time
import uuid
import json
from spotapi.types.annotations import enforce
from spotapi.types import Config
from spotapi.exceptions import GeneratorError
from spotapi.http.request import TLSClient
from spotapi.utils.strings import (
    random_email,
    random_string,
    parse_json_string,
    random_dob,
)

__all__ = ["Creator", "AccountChallenge", "GeneratorError"]


@enforce
class Creator:
    """
    Creates a new Spotify account.

    Parameters
    ----------
    cfg (Config): Configuration object.
    email (str, optional): Email address to use for the account. Defaults to a randomly generated email.
    display_name (str, optional): Display name to use for the account. Defaults to a randomly generated string.
    password (str, optional): Password to use for the account. Defaults to a randomly generated string.
    """

    __slots__ = (
        "email",
        "password",
        "display_name",
        "cfg",
        "client",
        "submission_id",
        "api_key",
        "installation_id",
        "csrf_token",
        "flow_id",
    )

    def __init__(
        self,
        cfg: Config,
        email: str = random_email(),
        display_name: str = random_string(10),
        password: str = random_string(10, strong=True),
    ) -> None:
        self.email = email
        self.password = password
        self.display_name = display_name
        self.cfg = cfg

        self.client = self.cfg.client
        self.submission_id = str(uuid.uuid4())

    def _get_session(self) -> None:
        url = "https://www.spotify.com/ca-en/signup"
        resp = self.client.get(url)

        if resp.fail:
            raise GeneratorError("Could not get session", error=resp.error.string)

        self.api_key = parse_json_string(resp.response, "signupServiceAppKey")
        self.installation_id = parse_json_string(resp.response, "spT")
        self.csrf_token = parse_json_string(resp.response, "csrfToken")
        self.flow_id = parse_json_string(resp.response, "flowId")

    def _process_register(self, captcha_token: str) -> None:
        payload = {
            "account_details": {
                "birthdate": random_dob(),
                "consent_flags": {
                    "eula_agreed": True,
                    "send_email": True,
                    "third_party_email": False,
                },
                "display_name": self.display_name,
                "email_and_password_identifier": {
                    "email": self.email,
                    "password": self.password,
                },
                "gender": 1,
            },
            "callback_uri": f"https://www.spotify.com/signup/challenge?flow_ctx={self.flow_id}%{int(time.time())}&locale=ca-en",
            "client_info": {
                "api_key": self.api_key,
                "app_version": "v2",
                "capabilities": [1],
                "installation_id": self.installation_id,
                "platform": "www",
            },
            "tracking": {
                "creation_flow": "",
                "creation_point": "spotify.com",
                "referrer": "",
            },
            "recaptcha_token": captcha_token,
            "submission_id": self.submission_id,
            "flow_id": self.flow_id,
        }
        url = "https://spclient.wg.spotify.com/signup/public/v2/account/create"

        resp = self.client.post(url, json=payload)

        if resp.fail:
            raise GeneratorError(
                "Could not process registration", error=resp.error.string
            )

        if "challenge" in resp.response:
            self.cfg.logger.attempt("Encountered Embedded Challenge. Defeating...")
            AccountChallenge(self.client, resp.response, self.cfg).defeat_challenge()

    def register(self) -> None:
        self._get_session()
        if self.cfg.solver is None:
            raise GeneratorError("Solver not set")

        captcha_token = self.cfg.solver.solve_captcha(
            "https://www.spotify.com/ca-en/signup",
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "website/signup/submit_email",
            "v3",
        )
        self._process_register(captcha_token)


class AccountChallenge:
    __slots__ = (
        "client",
        "raw",
        "session_id",
        "cfg",
        "challenge_url",
    )

    def __init__(self, client: TLSClient, raw_response: str, cfg: Config) -> None:
        self.client = client
        self.raw = raw_response
        self.session_id = parse_json_string(
            json.dumps(raw_response, separators=(",", ":")), "session_id"
        )
        self.cfg = cfg

    def _get_session(self) -> None:
        url = "https://challenge.spotify.com/api/v1/get-session"
        payload = {"session_id": self.session_id}
        resp = self.client.post(url, json=payload)

        if resp.fail:
            raise GeneratorError(
                "Could not get challenge session", error=resp.error.string
            )

        self.challenge_url = parse_json_string(
            json.dumps(resp.response, separators=(",", ":")), "url"
        )

    def _submit_challenge(self, token: str) -> None:
        session_id = self.challenge_url.split("c/")[1].split("/")[0]
        challenge_id = self.challenge_url.split(session_id + "/")[1].split("/")[0]
        url = "https://challenge.spotify.com/api/v1/invoke-challenge-command"
        payload = {
            "session_id": session_id,
            "challenge_id": challenge_id,
            "recaptcha_challenge_v1": {"solve": {"recaptcha_token": token}},
        }
        resp = self.client.post(
            url,
            json=payload,
            headers={
                "X-Cloud-Trace-Context": "000000000000000004ec7cfe60aa92b5/8088460714428896449;o=1"
            },
        )

        if resp.fail:
            raise GeneratorError("Could not submit challenge", error=resp.error.string)

    def _complete_challenge(self) -> None:
        url = (
            "https://spclient.wg.spotify.com/signup/public/v2/account/complete-creation"
        )
        payload = {"session_id": self.session_id}
        resp = self.client.post(url, json=payload)

        if resp.fail:
            raise GeneratorError(
                "Could not complete challenge", error=resp.error.string
            )

        if "success" not in resp.response:
            raise GeneratorError("Could not complete challenge", error=resp.response)

    def defeat_challenge(self) -> None:
        self._get_session()
        if self.cfg.solver is None:
            raise GeneratorError("Solver not set")

        token = self.cfg.solver.solve_captcha(
            self.challenge_url,
            "6LeO36obAAAAALSBZrY6RYM1hcAY7RLvpDDcJLy3",
            "challenge",
            "v3",
        )
        self._submit_challenge(token)
        self._complete_challenge()
        self.cfg.logger.info("Successfully defeated challenge. Account created.")
