"""Shared artwork and color dataclasses."""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = (
    "Sources",
    "ColorDark",
    "ExtractedColors",
    "EncoreBaseSetTextColor",
    "BackgroundBase",
    "BackgroundTintedBase",
    "TextBase",
    "TextBrightAccent",
    "TextSubdued",
    "HighContrast",
    "HigherContrast",
    "MinContrast",
    "ExtractedColorSet",
    "SquareCoverImage",
    "VisualIdentity",
)


@dataclass(slots=True)
class Sources:
    url: str
    height: int | None = None
    width: int | None = None


@dataclass(slots=True)
class ColorDark:
    hex: str | None = None
    is_fallback: bool | None = None


@dataclass(slots=True)
class ExtractedColors:
    color_dark: ColorDark | None = None


@dataclass(slots=True)
class EncoreBaseSetTextColor:
    alpha: int
    blue: int
    green: int
    red: int


@dataclass(slots=True)
class BackgroundBase:
    alpha: int
    blue: int
    green: int
    red: int


@dataclass(slots=True)
class BackgroundTintedBase:
    alpha: int
    blue: int
    green: int
    red: int


@dataclass(slots=True)
class TextBase:
    alpha: int
    blue: int
    green: int
    red: int


@dataclass(slots=True)
class TextBrightAccent:
    alpha: int
    blue: int
    green: int
    red: int


@dataclass(slots=True)
class TextSubdued:
    alpha: int
    blue: int
    green: int
    red: int


@dataclass(slots=True)
class HighContrast:
    background_base: BackgroundBase | None = None
    background_tinted_base: BackgroundTintedBase | None = None
    text_base: TextBase | None = None
    text_bright_accent: TextBrightAccent | None = None
    text_subdued: TextSubdued | None = None


@dataclass(slots=True)
class HigherContrast:
    background_base: BackgroundBase | None = None
    background_tinted_base: BackgroundTintedBase | None = None
    text_base: TextBase | None = None
    text_bright_accent: TextBrightAccent | None = None
    text_subdued: TextSubdued | None = None


@dataclass(slots=True)
class MinContrast:
    background_base: BackgroundBase | None = None
    background_tinted_base: BackgroundTintedBase | None = None
    text_base: TextBase | None = None
    text_bright_accent: TextBrightAccent | None = None
    text_subdued: TextSubdued | None = None


@dataclass(slots=True)
class ExtractedColorSet:
    encore_base_set_text_color: EncoreBaseSetTextColor | None = None
    high_contrast: HighContrast | None = None
    higher_contrast: HigherContrast | None = None
    min_contrast: MinContrast | None = None


@dataclass(slots=True)
class SquareCoverImage:
    extracted_color_set: ExtractedColorSet | None = None
    _typename: str | None = None


@dataclass(slots=True)
class VisualIdentity:
    """Optional search artwork metadata supplied by Spotify."""

    square_cover_image: SquareCoverImage | None = None


@dataclass(slots=True)
class CoverArt:
    extracted_colors: ExtractedColors | None = None
    sources: list[Sources] = field(default_factory=list[Sources])
