from __future__ import annotations

import math
import random
import asyncio
from datetime import timedelta
from typing import TYPE_CHECKING, Self, Unpack, ClassVar, Final, Sequence, Any

import wreq
from spotapi.v2.connection.types import (
    ResponseFailure,
    ResponseSuccess,
    DefaultOSList,
    DefaultProfileList,
    Methods,
)
from spotapi.v2.types import DefaultLogger
from spotapi.v2.datastruct import Pool, ObjectDict
from spotapi.v2.utils import random_with_weights

if TYPE_CHECKING:
    from spotapi.v2.connection.types import (
        Response,
        BackoffStrategy,
        JitterStrategy,
        EmulateBrowser,
        EmulateOS,
    )
    from spotapi.v2.types import LoggerProtocol
    from wreq import ClientConfig

__all__: tuple[str, ...] = (
    "HTTPClient",
    "ClientPool",
)

NON_RETRYABLE_STATUS_CODES = [
    400,  # Bad Request
    401,  # Unauthorized
    403,  # Forbidden
    404,  # Not Found
    405,  # Method Not Allowed
    406,  # Not Acceptable
    410,  # Gone
    411,  # Length Required
    412,  # Precondition Failed
    413,  # Payload Too Large
    414,  # URI Too Long
    415,  # Unsupported Media Type
    422,  # Unprocessable Content
    424,  # Failed Dependency
]

ClientPool: Pool[HTTPClient] = Pool(factory=lambda: HTTPClient(), teardown=lambda t: t.close())
_EMPTY_FAILURE: Final[ResponseFailure] = ResponseFailure(
    status_code=None, ok=False, text=None, json=None, location=None, headers=None
)


def _default_backoff(attempt: int) -> float:
    return float(attempt**2)


def _default_jitter(base_delay: float) -> float:
    return random.uniform(base_delay * 0.05, base_delay * 0.40)


class HTTPClient:
    _default_client_cfg: ClassVar[ClientConfig] = {
        "cookie_store": True,
        "gzip": True,
        "referer": True,
        "brotli": True,
        "deflate": True,
        "zstd": True,
        "timeout": timedelta(seconds=30),
        "redirect": wreq.redirect.Policy.limited(10),
    }

    __slots__: tuple[str, ...] = (
        "_wclient",
        "_logger",
        "_backoff",
        "_jitter",
        "_max_delay",
    )

    def __init__(
        self,
        *,
        backoff: BackoffStrategy = _default_backoff,
        jitter: JitterStrategy = _default_jitter,
        logger: LoggerProtocol = DefaultLogger,
        max_delay: float = 60.0,
        **kwargs: Unpack[wreq.ClientConfig],
    ) -> None:
        _default_emulation_profile: wreq.Emulation = self._create_new_emulation_profile()
        if not kwargs.get("emulation", None):
            kwargs["emulation"] = _default_emulation_profile

        self._wclient = wreq.Client(**{**self._default_client_cfg, **kwargs})
        self._logger = logger
        self._backoff = backoff
        self._jitter = jitter
        self._max_delay = max_delay

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.close()

    async def close(self) -> None:
        await asyncio.to_thread(self._wclient.close)

    def get_cookie(self, name: str) -> str | None:
        """Gets a cookie irrelavent of its domain"""
        if not self._wclient.cookie_jar:
            return

        for cookie in self._wclient.cookie_jar.get_all():
            if cookie.name.lower() == name.lower():
                return cookie.value

    @property
    def wclient(self) -> wreq.Client:
        return self._wclient

    @staticmethod
    def _create_new_emulation_profile(
        os_list: Sequence[EmulateOS] = DefaultOSList,
        profiles: Sequence[EmulateBrowser] = DefaultProfileList,
    ) -> wreq.Emulation:
        selected_os = random_with_weights(os_list, [os.weight for os in os_list])
        browser = random_with_weights(profiles, [p.weight for p in profiles])

        prefix = browser.browser_name.capitalize()
        valid_profiles: list[tuple[wreq.Profile, int]] = [
            # I don't think the enum pyi type is 1:1 with the internal rust src
            (getattr(wreq.Profile, name), version)
            for name in wreq.Profile.__dict__
            if name.startswith(prefix)
            and (suffix := name[len(prefix) :]).isdigit()
            and browser.min_version <= (version := int(suffix)) <= browser.max_version
        ]

        population, weights = zip(
            # favours newer versions
            *[(profile, math.exp(version / 5)) for profile, version in valid_profiles]
        )

        chosen_profile = random.choices(
            population=population,
            weights=weights,
        )[0]
        return wreq.Emulation(
            platform=selected_os.platform,
            profile=chosen_profile,
        )

    @staticmethod
    async def _parse_response(response: wreq.Response) -> Response:
        text = await response.text()
        try:
            json_data = await response.json()
        except Exception:
            json_data = None

        common = {
            "status_code": response.status,
            "text": text,
            "location": str(response.url),
            "headers": response.headers,
        }

        if response.status.is_success():
            return ResponseSuccess(
                ok=True,
                json=ObjectDict.from_json(json_data) if json_data else None,
                **common,
            )

        return ResponseFailure(
            ok=False,
            json=ObjectDict.from_json(json_data) if json_data else None,
            **common,
        )

    def _compute_delay(self, attempt: int) -> float:
        base: float = (
            self._backoff if isinstance(self._backoff, (int, float)) else self._backoff(attempt)
        )

        jitter: float = 0.0
        if self._jitter is not None:
            jitter = self._jitter if isinstance(self._jitter, (int, float)) else self._jitter(base)

        return min(base + jitter, self._max_delay)

    async def request(
        self,
        method: Methods,
        url: str,
        *,
        retries: int = 3,
        **kwargs: Unpack[wreq.Request],
    ) -> Response:
        last_response: Response | None = None

        for attempt in range(retries):
            is_final = attempt == (retries - 1)
            try:
                raw = await self._wclient.request(
                    getattr(wreq.Method, method.upper()), url, **kwargs
                )
                response = await self._parse_response(raw)

                if response.ok or (
                    response.status_code
                    and response.status_code.as_int() in NON_RETRYABLE_STATUS_CODES
                ):
                    return response

                last_response = response
                self._logger.debug(
                    "Non success status received",
                    status_code=(
                        response.status_code.as_int() if response.status_code is not None else None
                    ),
                    attempt=attempt,
                    retrying=not is_final,
                )

            except Exception as exc:
                self._logger.debug(
                    "Exception raised during request",
                    exception=str(exc),
                    attempt=attempt,
                    retrying=not is_final,
                )

            if not is_final:
                await asyncio.sleep(self._compute_delay(attempt))

        return last_response or _EMPTY_FAILURE

    async def get(self, url: str, **kwargs: Unpack[wreq.Request]) -> Response:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs: Unpack[wreq.Request]) -> Response:
        return await self.request("POST", url, **kwargs)

    async def put(self, url: str, **kwargs: Unpack[wreq.Request]) -> Response:
        return await self.request("PUT", url, **kwargs)

    async def patch(self, url: str, **kwargs: Unpack[wreq.Request]) -> Response:
        return await self.request("PATCH", url, **kwargs)

    async def delete(self, url: str, **kwargs: Unpack[wreq.Request]) -> Response:
        return await self.request("DELETE", url, **kwargs)

    async def head(self, url: str, **kwargs: Unpack[wreq.Request]) -> Response:
        return await self.request("HEAD", url, **kwargs)
