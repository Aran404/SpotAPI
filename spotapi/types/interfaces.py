from typing import Any, List, Literal, Mapping, Optional, Protocol
from typing_extensions import runtime_checkable
from spotapi.http.request import StdClient


@runtime_checkable
class CaptchaProtocol(Protocol):
    def __init__(
        self: "CaptchaProtocol",
        api_key: str,
        client: Optional[StdClient] = StdClient(3),
        *,
        proxy: Optional[str] = None,
        retries: Optional[int] = 120,
    ) -> None:
        ...
    
    def get_balance(self: "CaptchaProtocol") -> float | None:
        ...

    def solve_captcha(
        self: "CaptchaProtocol",
        url: str,
        site_key: str,
        action: str,
        task: Literal["v2", "v3"],
    ) -> str:
        ...


@runtime_checkable
class LoggerProtocol(Protocol):
    @staticmethod
    def info(s: str, **extra) -> None:
        ...

    @staticmethod
    def attempt(s: str, **extra) -> None:
        ...

    @staticmethod
    def error(s: str, **extra) -> None:
        ...

    @staticmethod
    def fatal(s: str, **extra) -> None:
        ...


@runtime_checkable
class SaverProtocol(Protocol):
    def __init__(
        self: "SaverProtocol", *args, **kwargs
    ) -> None:
        ...
        
    def save(self: "SaverProtocol", data: List[Mapping[str, Any]], **kwargs) -> None:
        ...

    def load(self: "SaverProtocol", query: Mapping[str, Any], **kwargs) -> Mapping[str, Any]:
        ...

    def delete(self: "SaverProtocol", query: Mapping[str, Any], **kwargs) -> None:
        ...
