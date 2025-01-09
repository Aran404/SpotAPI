from __future__ import annotations

from typing import Any, List, Literal, Mapping, Protocol
from typing_extensions import runtime_checkable
from spotapi.http.request import StdClient

__all__ = ["CaptchaProtocol", "LoggerProtocol", "SaverProtocol"]


@runtime_checkable
class CaptchaProtocol(Protocol):
    def __init__(
        self: "CaptchaProtocol",
        api_key: str,
        client: StdClient = StdClient(3),
        *,
        retries: int = 120,
        proxy: str | None = None,
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
    def info(s: str, **extra: Any) -> None:
        ...

    @staticmethod
    def attempt(s: str, **extra: Any) -> None:
        ...

    @staticmethod
    def error(s: str, **extra: Any) -> None:
        ...

    @staticmethod
    def fatal(s: str, **extra: Any) -> None:
        ...


@runtime_checkable
class SaverProtocol(Protocol):
    def __init__(self: "SaverProtocol", *args: Any, **kwargs: Any) -> None:
        ...

    def save(
        self: "SaverProtocol", data: List[Mapping[str, Any]], **kwargs: Any
    ) -> None:
        ...

    def load(
        self: "SaverProtocol", query: Mapping[str, Any], **kwargs: Any
    ) -> Mapping[str, Any]:
        ...

    def delete(self: "SaverProtocol", query: Mapping[str, Any], **kwargs: Any) -> None:
        ...
