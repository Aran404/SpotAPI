"""JSON-safe export of typed result values without implicit network access."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, cast

from .types import HTTPError


def to_dict(value: object) -> Any:
    """Recursively export dataclasses, dates, enums and JSON-shaped containers.

    Python field names are preserved. Dates use ISO format, tuples become
    lists, and unsupported objects/non-finite numbers raise TypeError rather
    than being converted to invented strings. The caller chooses what to
    export; personal account-model fields are included when explicitly passed.
    Exceptions export only their type and HTTP status, never message text.
    """
    if isinstance(value, Exception):
        result: dict[str, Any] = {"type": type(value).__name__}
        if isinstance(value, HTTPError):
            result["status_code"] = value.status_code
        return result
    if isinstance(value, Enum):
        return to_dict(value.value)
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise TypeError("Non-finite numbers cannot be exported as JSON")
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: to_dict(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value)
        if any(not isinstance(key, str) for key in items):
            raise TypeError("JSON object keys must be strings")
        return {cast(str, key): to_dict(item) for key, item in items.items()}
    if isinstance(value, (list, tuple)):
        return [to_dict(item) for item in cast(list[object] | tuple[object, ...], value)]
    raise TypeError(f"Cannot export {type(value).__name__} as JSON")
