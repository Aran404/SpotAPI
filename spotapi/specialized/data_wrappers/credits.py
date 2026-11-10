"""Song contributors as reported by Spotify."""

from dataclasses import dataclass

__all__ = ("Credit", "TrackCredits")


@dataclass(slots=True)
class CreditGroup:
    name: str


@dataclass(slots=True)
class Credit:
    name: str
    role: str | None = None
    uri: str | None = None
    role_group: CreditGroup | None = None


@dataclass(slots=True, frozen=True)
class TrackCredits:
    uri: str
    contributors: tuple[Credit, ...]

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        return f"<TrackCredits uri={self.uri!r} contributors={len(self.contributors)}>"
