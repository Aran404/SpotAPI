from __future__ import annotations

from dataclasses import dataclass

__all__: tuple[str, ...] = (
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
    hex: str
    is_fallback: bool


@dataclass(slots=True)
class ExtractedColors:
    color_dark: ColorDark


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
    background_base: BackgroundBase
    background_tinted_base: BackgroundTintedBase
    text_base: TextBase
    text_bright_accent: TextBrightAccent
    text_subdued: TextSubdued


@dataclass(slots=True)
class HigherContrast:
    background_base: BackgroundBase
    background_tinted_base: BackgroundTintedBase
    text_base: TextBase
    text_bright_accent: TextBrightAccent
    text_subdued: TextSubdued


@dataclass(slots=True)
class MinContrast:
    background_base: BackgroundBase
    background_tinted_base: BackgroundTintedBase
    text_base: TextBase
    text_bright_accent: TextBrightAccent
    text_subdued: TextSubdued


@dataclass(slots=True)
class ExtractedColorSet:
    encore_base_set_text_color: EncoreBaseSetTextColor
    high_contrast: HighContrast
    higher_contrast: HigherContrast
    min_contrast: MinContrast


@dataclass(slots=True)
class SquareCoverImage:
    extracted_color_set: ExtractedColorSet
    _typename: str | None = None


@dataclass(slots=True)
class VisualIdentity:
    square_cover_image: SquareCoverImage


@dataclass(slots=True)
class CoverArt:
    extracted_colors: ExtractedColors
    sources: list[Sources]
