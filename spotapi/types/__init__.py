"""Exceptions, logger interfaces, and the default SpotAPI logger."""

from __future__ import annotations

import logging

from .exceptions import (
    BaseClientError,
    HTTPError,
    PlaylistError,
    SpotAPIError,
    WebsocketError,
)
from .logger import (
    InbuiltLogger,
    JsonLogger,
    Level,
    LoggerColour,
    LoggerMixin,
    LoggerProtocol,
    MultiLogger,
    NoopLogger,
    StandardLogger,
)

DefaultLogger: LoggerProtocol = InbuiltLogger(logging.getLogger("spotapi"))

__all__ = (
    "SpotAPIError",
    "BaseClientError",
    "HTTPError",
    "PlaylistError",
    "WebsocketError",
    "DefaultLogger",
    "InbuiltLogger",
    "JsonLogger",
    "Level",
    "LoggerColour",
    "LoggerMixin",
    "LoggerProtocol",
    "MultiLogger",
    "NoopLogger",
    "StandardLogger",
)
