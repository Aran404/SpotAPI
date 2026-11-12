"""Song contributors as reported by Spotify."""

from dataclasses import dataclass

__all__ = ("Credit", "TrackCredits")


@dataclass(slots=True)
class CreditGroup:
    name: str


@dataclass(slots=True)
class Credit:
    """One contributor and their role as reported by Spotify.

    The contributor URI and role group are optional. Use a supplied URI when
    comparing identity across songs rather than assuming names are unique.
    """

    name: str
    role: str | None = None
    uri: str | None = None
    role_group: CreditGroup | None = None


@dataclass(slots=True, frozen=True)
class TrackCredits:
    """Contributors reported for one track, preserving each supplied role.

    The same person can appear with different roles or groups. This model
    contains the fetched credits and performs no follow-up queries.
    """

    uri: str
    contributors: tuple[Credit, ...]

    def __repr__(self) -> str:
        return f"<TrackCredits uri={self.uri!r} contributors={len(self.contributors)}>"
