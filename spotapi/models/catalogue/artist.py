"""Typed artist results from Spotify search."""

from __future__ import annotations

from dataclasses import dataclass

from .common import (
    ExtractedColors,
    Sources,
    VisualIdentity,
)

__all__ = ("Artist",)


@dataclass(slots=True)
class Verification:
    is_verified: bool | None = None


@dataclass(slots=True)
class OnPlatformReputationTrait:
    verification: Verification | None = None


@dataclass(slots=True)
class ArtistProfile:
    name: str


@dataclass(slots=True)
class AvatarImage:
    extracted_colors: ExtractedColors | None = None
    sources: list[Sources] | None = None


@dataclass(slots=True)
class Visuals:
    avatar_image: AvatarImage | None = None


@dataclass(slots=True)
class Artist:
    """Artist search result with an always-present display name and URI.

    Attributes:
        profile: Artist name.
        uri: Full Spotify artist URI.
        visuals: Optional avatar artwork.
    """

    profile: ArtistProfile
    uri: str
    on_platform_reputation_trait: OnPlatformReputationTrait | None = None
    visual_identity: VisualIdentity | None = None
    visuals: Visuals | None = None

    @property
    def name(self) -> str:
        """Artist display name, exposed without unpacking ``profile``."""
        return self.profile.name

    @property
    def id(self) -> str:
        """Spotify artist ID, derived from the canonical URI."""
        return self.uri.rsplit(":", 1)[-1]

    def __repr__(self) -> str:
        reputation = self.on_platform_reputation_trait
        verification = reputation.verification if reputation else None
        verified = verification.is_verified if verification else None

        return f"<Artist name={self.profile.name!r} verified={verified!r} uri={self.uri!r}>"
