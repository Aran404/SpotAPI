from dataclasses import dataclass, field
from typing import Any, Union
from tls_client.response import Response as TLSResponse

# Dataclass needs to be here to avoid circular imports
@dataclass
class Response:
    raw: TLSResponse
    status_code: int
    response: Any

    error: "Error" = field(init=False)
    success: bool = field(init=False)
    fail: bool = field(init=False)

    def __post_init__(self):
        self.error = Error(
            self.status_code,
            self.response,
            f"Status Code: {self.status_code}, Response: {self.response}",
        )
        self.success = self.error.is_success
        self.fail = not self.success


@dataclass
class Error:
    status_code: int
    response: Union[str, dict]
    string: str

    @property
    def is_success(self) -> bool:
        return 200 <= self.status_code <= 302

    @property
    def is_fail(self) -> bool:
        return not self.is_success
