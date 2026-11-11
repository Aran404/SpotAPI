"""Public types for the SpotAPI HTTP layer."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Literal, NamedTuple, TypeAlias

from wreq import Platform, StatusCode

from spotapi.datastruct import ObjectDict

__all__ = (
    "BackoffStrategy",
    "DefaultOSList",
    "DefaultProfileList",
    "EmulateBrowser",
    "EmulateOS",
    "JitterStrategy",
    "Methods",
    "Response",
)

BackoffStrategy: TypeAlias = float | Callable[[int], float]
JitterStrategy: TypeAlias = float | Callable[[float], float] | None

Methods: TypeAlias = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "HEAD", "OPTIONS", "TRACE"]


@dataclass(slots=True, frozen=True)
class Response:
    """A completed HTTP exchange.

    Transport failures (timeouts, DNS errors, ...) raise instead of producing a
    ``Response``, so every field is always populated.

    Attributes:
        status_code: Final status after redirects.
        text: Decoded response body.
        url: Final URL after redirects.
        headers: Response headers with lowercase names.
        json: The body as an ``ObjectDict`` when it is a JSON *object*;
            ``None`` for anything else (including JSON arrays).
    """

    status_code: StatusCode
    text: str
    url: str
    headers: Mapping[str, str]
    json: ObjectDict | None
    body: bytes = b""

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<Response status={self.status_code.as_int()}>"

    @property
    def ok(self) -> bool:
        """Whether the status code is 2xx."""
        return self.status_code.is_success()


class EmulateOS(NamedTuple):
    platform: Platform
    weight: float


class EmulateBrowser(NamedTuple):
    browser_name: str
    min_version: int
    max_version: int
    weight: float


DefaultOSList: tuple[EmulateOS, ...] = (
    EmulateOS(Platform.Windows, 30),
    EmulateOS(Platform.MacOS, 6),
    EmulateOS(Platform.Linux, 2),
)
DefaultProfileList: tuple[EmulateBrowser, ...] = (
    EmulateBrowser("chrome", 120, 147, 67),
    EmulateBrowser("edge", 122, 147, 6),
    EmulateBrowser("firefox", 117, 149, 3),
    EmulateBrowser("opera", 120, 130, 2),
)
