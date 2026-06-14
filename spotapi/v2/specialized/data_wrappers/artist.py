from __future__ import annotations

from dataclasses import dataclass

from spotapi.v2.specialized.data_wrappers.common import (
    ExtractedColors,
    Sources,
    VisualIdentity,
)

__all__: tuple[str, ...] = ("Artist",)


@dataclass(slots=True)
class Verification:
    is_verified: bool


@dataclass(slots=True)
class OnPlatformReputationTrait:
    verification: Verification


@dataclass(slots=True)
class ArtistProfile:
    name: str


@dataclass(slots=True)
class AvatarImage:
    extracted_colors: ExtractedColors
    sources: list[Sources]


@dataclass(slots=True)
class Visuals:
    avatar_image: AvatarImage


@dataclass(slots=True)
class Artist:
    """A Spotify artist returned by the search API.

    Attributes
    ----------
    uri : str
        Spotify URI (``spotify:artist:<id>``).
    profile : ArtistProfile
        Artist display name and metadata.
    visuals : Visuals
        Avatar image sources and color data.
    on_platform_reputation_trait : OnPlatformReputationTrait
        Verification badge status.
    visual_identity : VisualIdentity
        Theme color set extracted from the artist's image.
    """

    on_platform_reputation_trait: OnPlatformReputationTrait
    profile: ArtistProfile
    uri: str
    visual_identity: VisualIdentity
    visuals: Visuals

    def __repr__(self) -> str:
        verified = self.on_platform_reputation_trait.verification.is_verified
        return f"<Artist name={self.profile.name!r}" f" verified={verified}" f" uri={self.uri!r}>"
