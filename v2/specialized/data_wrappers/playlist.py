from typing import Any
from dataclasses import dataclass


@dataclass(slots=True)
class ColorDark:
    hex: str
    is_fallback: bool


@dataclass(slots=True)
class ExtractedColors:
    color_dark: ColorDark


@dataclass(slots=True)
class Sources:
    url: str
    height: str | None = None
    width: str | None = None


@dataclass(slots=True)
class Items:
    extracted_colors: ExtractedColors
    sources: list[Sources]


@dataclass(slots=True)
class Images:
    items: list[Items]


@dataclass(slots=True)
class Avatar:
    sources: list[Sources]


@dataclass(slots=True)
class Data:
    _typename: str
    avatar: Avatar
    name: str
    uri: str
    username: str


@dataclass(slots=True)
class OwnerV2:
    _typename: str
    data: Data


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


@dataclass(slots=True)
class VisualIdentity:
    square_cover_image: SquareCoverImage


@dataclass(slots=True)
class Playlist:
    attributes: list[Any]
    description: str
    format: str
    images: Images
    name: str
    owner_v2: OwnerV2
    uri: str
    visual_identity: VisualIdentity
