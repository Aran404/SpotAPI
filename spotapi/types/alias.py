from __future__ import annotations

from typing_extensions import TypeAlias, Self
from typing import Final, final, Any


__all__ = ["_UndefinedType", "_Undefined", "_UStr"]


@final
class _UndefinedType:
    def __copy__(self) -> Self:
        return self

    def __deepcopy__(self, memo) -> Self:
        return self

    def __bool__(self) -> bool:
        return False

    def __eq__(self, other: object) -> bool:
        return isinstance(other, _UndefinedType)

    def __ne__(self, other: object) -> bool:
        return not isinstance(other, _UndefinedType)


_Undefined: Final[Any] = _UndefinedType()
_UStr: TypeAlias = str | _UndefinedType
