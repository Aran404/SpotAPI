import time
from typing import Literal, Optional, Dict, Any

from spotapi.exceptions import CaptchaException, SolverError
from spotapi.http.request import StdClient

__all__ = ["Capsolver", "CaptchaException", "SolverError"]


class Capsolver:
    BaseURL = "https://api.capsolver.com/"

    def __init__(
        self,
        api_key: str,
        client: StdClient = StdClient(3),
        *,
        retries: int = 120,
        proxy: Optional[str] = None,
    ) -> None:
        self.api_key = api_key
        self.client = client
        self.proxy = proxy
        self.retries = retries

        self.client.authenticate = lambda kwargs: self._auth_rule(kwargs)

    def _auth_rule(self, kwargs: dict) -> dict:
        if "json" not in kwargs:
            kwargs["json"] = {}

        kwargs["json"]["clientKey"] = self.api_key
        return kwargs

    def get_balance(self) -> float | None:
        endpoint = self.BaseURL + "getBalance"
        request = self.client.post(endpoint, authenticate=True)

        if request.fail:
            raise CaptchaException(
                "Could not retrieve balance.", error=request.error.string
            )

        resp = request.response

        if int(resp["errorId"]) != 0:
            raise CaptchaException(
                "Could not retrieve balance.", error=resp["errorDescription"]
            )

        return resp["balance"]

    def _create_task(
        self,
        url: str,
        site_key: str,
        action: str,
        task: Literal["v2", "v3"],
        proxy: Optional[str] = None,
    ) -> str:
        endpoint = self.BaseURL + "createTask"
        task_type = (
            "ReCaptcha{}EnterpriseTask"
            if proxy
            else "ReCaptcha{}EnterpriseTaskProxyLess"
        ).format(task.upper())
        payload: Dict[str, Dict[str, Any]] = {
            "task": {
                "type": task_type,
                "websiteURL": url,
                "websiteKey": site_key,
                "pageAction": action,
            },
        }

        if task == "v2":
            payload["task"]["isInvisible"] = True

        if proxy:
            payload["task"]["proxy"] = proxy

        request = self.client.post(endpoint, authenticate=True, json=payload)

        if request.fail:
            raise CaptchaException("Could not create task.", error=request.error.string)

        resp = request.response

        if int(resp["errorId"]) != 0:
            raise CaptchaException(
                "Could not create task.", error=resp["errorDescription"]
            )

        return str(resp["taskId"])

    def _harvest_task(self, task_id: str, retries: int) -> str:
        for _ in range(retries):
            payload = {"taskId": task_id}
            endpoint = self.BaseURL + "getTaskResult"

            request = self.client.post(endpoint, authenticate=True, json=payload)

            if request.fail:
                raise CaptchaException(
                    "Could not get task result", error=request.error.string
                )

            resp = request.response

            if int(resp["errorId"]) != 0:
                raise CaptchaException(
                    "Could not get task result.", error=resp["errorDescription"]
                )

            if resp["status"] == "ready":
                return str(resp["solution"]["gRecaptchaResponse"])

            time.sleep(1)
            continue

        raise SolverError("Failed to solve captcha.", error="Max retries reached")

    def solve_captcha(
        self,
        url: str,
        site_key: str,
        action: str,
        task: Literal["v2", "v3"],
    ) -> str:
        task_id = self._create_task(url, site_key, action, task, self.proxy)
        return self._harvest_task(task_id, self.retries)
