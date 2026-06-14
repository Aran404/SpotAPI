from .logger import *
from .exceptions import *

from v2.types import logger, exceptions
from .logger import *
from .exceptions import *
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from types import ModuleType

DefaultLogger: LoggerProtocol = LoggerColour()

__modules__: tuple[ModuleType, ...] = (
    logger,
    exceptions,
)
__all__: list[str] = [name for m in __modules__ for name in getattr(m, "__all__", [])]  # type: ignore[operation]
