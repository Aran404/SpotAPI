"""Credential-free metadata for an explicitly saved session."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SessionInfo:
    """Cookie-free saved-session metadata; presence is not proof of validity."""

    name: str
    present: bool
