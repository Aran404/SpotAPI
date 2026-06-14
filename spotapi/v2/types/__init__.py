from spotapi.v2.types import logger, exceptions
from spotapi.v2.types.logger import *
from spotapi.v2.types.exceptions import *
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

DefaultLogger: LoggerProtocol = LoggerColour()

__modules__: tuple[ModuleType, ...] = (
    logger,
    exceptions,
)
__all__: list[str] = [name for m in __modules__ for name in getattr(m, "__all__", [])]  # type: ignore[operation]
