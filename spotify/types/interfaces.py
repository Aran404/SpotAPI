from typing import Optional, Protocol, Literal
from typing_extensions import runtime_checkable
from spotify.http.request import StdClient


@runtime_checkable
class CaptchaProtocol(Protocol):
    def __init__(
        self,
        api_key: str,
        client: Optional[StdClient] = StdClient(3),
        *,
        proxy: Optional[str] = None,
        retries: Optional[int] = 120,
    ) -> None:
        ...

    def get_balance(self) -> float | None:
        ...

    def solve_captcha(
        self,
        url: str,
        site_key: str,
        action: str,
        task: Literal["v2", "v3"],
    ) -> str:
        ...


class LoggerProtocol(Protocol):
    @staticmethod
    def info(s: str, **extra) -> None:
        ...

    @staticmethod
    def error(s: str, **extra) -> None:
        ...

    @staticmethod
    def fatal(s: str, **extra) -> None:
        ...
