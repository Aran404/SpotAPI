"""Input-aligned batch results without ownership of network work."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar, cast

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class BatchItem(Generic[T]):
    """One input's value or exception; cancellation always propagates.

    ``index`` preserves duplicate inputs and original order. Check ``ok`` or
    use ``unwrap()`` to return the value or raise its original exception.
    """

    index: int
    value: str
    result: T | None = None
    error: Exception | None = None

    @property
    def ok(self) -> bool:
        """Whether the read completed, including a legitimate None result."""
        return self.error is None

    def unwrap(self) -> T:
        """Return the successful value, otherwise raise the captured exception."""
        if self.error is not None:
            raise self.error
        return cast(T, self.result)
