from enum import Enum
from typing import Dict, Final


class ErrorSeverity(Enum):
    Fatal = 0
    Retry = 1
    EndThread = 2


class ResourceType(Enum):
    Email = 0
    Card = 1
    Proxy = 2
    All = 3


error_severity: Final[Dict[str | int, dict[str, int]]] = {
    "Status Code: 401, Response: {'error': 'Unauthorized'}": {
        "status": ErrorSeverity.Fatal,
    },
    "Status Code: 404, Response: {'error': 'No stock'}": {
        "status": ErrorSeverity.Retry,
        "resource": ResourceType.All,
    },
    "User doesn't exist": {"status": ErrorSeverity.Fatal},
}
