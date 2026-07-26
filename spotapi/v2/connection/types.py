from __future__ import annotations

from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Callable,
    Final,
    Literal,
    NamedTuple,
    TypeAlias,
    Mapping,
    Any,
)
from wreq import Platform, StatusCode

if TYPE_CHECKING:
    from spotapi.v2.datastruct import ObjectDict

__all__: tuple[str, ...] = (
    "BackoffStrategy",
    "JitterStrategy",
    "ResponseSuccess",
    "ResponseFailure",
    "Response",
)

BackoffStrategy: TypeAlias = float | Callable[[int], float]
JitterStrategy: TypeAlias = float | Callable[[float], float] | None
Response: TypeAlias = "ResponseSuccess | ResponseFailure"

Methods = Literal["GET", "POST", "DELETE", "PATCH", "PUT", "HEAD", "OPTIONS", "TRACE"]


@dataclass(slots=True, frozen=True)
class ResponseSuccess:
    status_code: StatusCode
    text: str
    location: str
    headers: Mapping[str, Any]
    json: Final[ObjectDict] | None
    ok: Final[Literal[True]] = True


@dataclass(slots=True, frozen=True)
class ResponseFailure:
    status_code: StatusCode | None
    text: str | None
    location: str | None
    headers: Mapping[str, Any] | None
    json: Final[ObjectDict] | None
    ok: Final[Literal[False]] = False


class EmulateOS(NamedTuple):
    platform: Platform
    weight: float


class EmulateBrowser(NamedTuple):
    browser_name: str
    min_version: int
    max_version: int
    weight: float


DefaultOSList: list[EmulateOS] = [
    EmulateOS(Platform.Windows, 30),
    EmulateOS(Platform.MacOS, 6),
    EmulateOS(Platform.Linux, 2),
]
DefaultProfileList: list[EmulateBrowser] = [
    EmulateBrowser("chrome", 120, 147, 67),
    EmulateBrowser("edge", 122, 147, 6),
    EmulateBrowser("firefox", 117, 149, 3),
    EmulateBrowser("opera", 120, 130, 2),
]
