from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__: tuple[str, ...] = ("Profile",)


@dataclass(slots=True)
class Profile:
    accountId: str
    avatar: str | None
    avatarBackgroundColor: int | None
    name: str
    socialHandle: str | None
    uri: str
    username: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Profile:
        return cls(
            accountId=data["accountId"],
            avatar=data.get("avatar"),
            avatarBackgroundColor=data.get("avatarBackgroundColor"),
            name=data["name"],
            socialHandle=data.get("socialHandle"),
            uri=data["uri"],
            username=data["username"],
        )
