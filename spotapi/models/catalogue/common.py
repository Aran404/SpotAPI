"""Shared artwork and color dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = (
    "RGBA",
    "ColorDark",
    "ContrastPalette",
    "CoverArt",
    "ExtractedColorSet",
    "ExtractedColors",
    "Sources",
    "SquareCoverImage",
    "VisualIdentity",
)


@dataclass(slots=True)
class Sources:
    """One artwork URL with optional pixel dimensions; no image data is fetched."""

    url: str
    height: int | None = None
    width: int | None = None


@dataclass(slots=True)
class ColorDark:
    """An optional extracted dark color and Spotify's fallback indicator."""

    hex: str | None = None
    is_fallback: bool | None = None


@dataclass(slots=True)
class ExtractedColors:
    """Extracted artwork colors, which may be absent for partial metadata."""

    color_dark: ColorDark | None = None


@dataclass(slots=True)
class RGBA:
    """A Spotify palette color with native integer alpha, blue, green and red channels."""

    alpha: int
    blue: int
    green: int
    red: int


@dataclass(slots=True)
class ContrastPalette:
    """Optional background and text colors for one Spotify contrast level."""

    background_base: RGBA | None = None
    background_tinted_base: RGBA | None = None
    text_base: RGBA | None = None
    text_bright_accent: RGBA | None = None
    text_subdued: RGBA | None = None


@dataclass(slots=True)
class ExtractedColorSet:
    """Optional text color and palettes for Spotify's three contrast levels."""

    encore_base_set_text_color: RGBA | None = None
    high_contrast: ContrastPalette | None = None
    higher_contrast: ContrastPalette | None = None
    min_contrast: ContrastPalette | None = None


@dataclass(slots=True)
class SquareCoverImage:
    """Square-artwork palette metadata, distinct from downloadable image sources."""

    extracted_color_set: ExtractedColorSet | None = None
    _typename: str | None = None


@dataclass(slots=True)
class VisualIdentity:
    """Optional search artwork metadata supplied by Spotify."""

    square_cover_image: SquareCoverImage | None = None


@dataclass(slots=True)
class CoverArt:
    """Available artwork sources and optional extracted presentation colors."""

    extracted_colors: ExtractedColors | None = None
    sources: list[Sources] = field(default_factory=list[Sources])
