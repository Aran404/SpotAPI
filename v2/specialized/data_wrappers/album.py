from dataclasses import dataclass


@dataclass(slots=True)
class Profile:
    name: str


@dataclass(slots=True)
class Items:
    profile: Profile
    uri: str


@dataclass(slots=True)
class Artists:
    items: list[Items]


@dataclass(slots=True)
class ColorDark:
    hex: str
    is_fallback: bool


@dataclass(slots=True)
class ExtractedColors:
    color_dark: ColorDark


@dataclass(slots=True)
class Sources:
    height: int
    url: str
    width: int


@dataclass(slots=True)
class CoverArt:
    extracted_colors: ExtractedColors
    sources: list[Sources]


@dataclass(slots=True)
class Date:
    year: int


@dataclass(slots=True)
class Playability:
    playable: bool
    reason: str


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
    _typename: str
    extracted_color_set: ExtractedColorSet


@dataclass(slots=True)
class VisualIdentity:
    square_cover_image: SquareCoverImage


@dataclass(slots=True)
class Album:
    artists: Artists
    cover_art: CoverArt
    date: Date
    is_album_pre_release: bool
    name: str
    playability: Playability
    type: str
    uri: str
    visual_identity: VisualIdentity
    pre_release_end_date_time: str | None = None
