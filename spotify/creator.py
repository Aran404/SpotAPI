import time
import uuid
from typing import Any, Optional
from spotify.data.data import Config
from spotify.exceptions.errors import GeneratorError
from spotify.http.request import TLSClient
from spotify.utils.strings import (
    random_email,
    random_string,
    parse_json_string,
    random_dob,
)


class Creator:
    def __init__(
        self,
        cfg: Config,
        email: Optional[str] = random_email(),
        password: Optional[str] = random_string(10, True),
        client: Optional[TLSClient] = TLSClient("chrome_120", "", auto_retries=3),
    ) -> None:
        self.client = client
        self.email = email
        self.password = password
        self.cfg = cfg
        self.submission_id = str(uuid.uuid4())

    def __get_session(self) -> None:
        url = "https://www.spotify.com/us-en/signup"
        request = self.client.get(url)

        if request.fail:
            raise GeneratorError("Could not get session", error=request.error.string)

        self.api_key = parse_json_string(request.response, "signupServiceAppKey")
        self.installation_id = parse_json_string(request.response, "spT")
        self.csrf_token = parse_json_string(request.response, "csrfToken")
        self.flow_id = parse_json_string(request.response, "flowId")

    def __process_register(self, captcha_token: str) -> None:
        payload = {
            "account_details": {
                "birthdate": random_dob(),
                "consent_flags": {
                    "eula_agreed": True,
                    "send_email": True,
                    "third_party_email": False,
                },
                "display_name": "Aran",
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

        request = self.client.post(url, json=payload)

        if request.fail:
            raise GeneratorError(
                "Could not process registration", error=request.error.string
            )

        if "challenge" in request.response:
            self.cfg.logger.attempt("Encountered Embedded Challenge. Defeating...")
            AccountChallenge(self.client, request.response, self.cfg).defeat_challenge()

    def register(self) -> None:
        self.__get_session()
        captcha_token = self.cfg.solver.solve_captcha(
            self.api_key,
            "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39",
            "website/signup/submit_email",
            "v3",
        )
        self.__process_register(captcha_token)


class AccountChallenge:
    def __init__(self, client: TLSClient, raw_response: str, cfg: Config) -> None:
        self.client = client
        self.raw = raw_response
        self.session_id = parse_json_string(raw_response, "session_id")
        self.cfg = cfg

    def __get_session(self) -> None:
        url = "https://challenge.spotify.com/api/v1/get-session"
        payload = {"session_id": self.session_id}
        request = self.client.post(url, json=payload)

        if request.fail:
            raise GeneratorError(
                "Could not get challenge session", error=request.error.string
            )

        self.challenge_url = parse_json_string(request.response, "url")

    def __submit_challenge(self, token: str) -> None:
        session_id = self.challenge_url.split("c/")[1].split("/")[0]
        challenge_id = self.challenge_url.split(session_id + "/")[1].split("/")[0]
        url = "https://challenge.spotify.com/api/v1/invoke-challenge-command"
        payload = {
            "session_id": session_id,
            "challenge_id": challenge_id,
            "recaptcha_challenge_v1": {"solve": {"recaptcha_token": token}},
        }
        request = self.client.post(
            url,
            json=payload,
            headers={
                "X-Cloud-Trace-Context": "000000000000000004ec7cfe60aa92b5/8088460714428896449;o=1"
            },
        )

        if request.fail:
            raise GeneratorError(
                "Could not submit challenge", error=request.error.string
            )

    def __complete_challenge(self) -> None:
        url = (
            "https://spclient.wg.spotify.com/signup/public/v2/account/complete-creation"
        )
        payload = {"session_id": self.session_id}
        request = self.client.post(url, json=payload)

        if request.fail:
            raise GeneratorError(
                "Could not complete challenge", error=request.error.string
            )

        if not ("success" in request.response):
            raise GeneratorError("Could not complete challenge", error=request.response)

    def defeat_challenge(self) -> None:
        self.__get_session()
        token = self.cfg.solver.solve_captcha(
            self.challenge_url,
            "6LeO36obAAAAALSBZrY6RYM1hcAY7RLvpDDcJLy3",
            "challenge",
            "v2",
        )
        self.__submit_challenge(token)
        self.__complete_challenge()
        self.cfg.logger.info("Successfully defeated challenge. Account created.")