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
    height: int
    url: str
    width: int


@dataclass(slots=True)
class CoverArt:
    extracted_colors: ExtractedColors
    sources: list[Sources]


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
class AlbumOfTrack:
    cover_art: CoverArt
    id: str
    name: str
    uri: str
    visual_identity: VisualIdentity


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
class AudioAssociations:
    total_count: int


@dataclass(slots=True)
class VideoAssociations:
    total_count: int


@dataclass(slots=True)
class AssociationsV3:
    audio_associations: AudioAssociations
    video_associations: VideoAssociations


@dataclass(slots=True)
class ContentRating:
    label: str


@dataclass(slots=True)
class Duration:
    total_milliseconds: int


@dataclass(slots=True)
class Playability:
    playable: bool
    reason: str


@dataclass(slots=True)
class Track:
    album_of_track: AlbumOfTrack
    artists: Artists
    associations_v3: AssociationsV3
    content_rating: ContentRating
    duration: Duration
    id: str
    track_media_type: str
    name: str
    playability: Playability
    uri: str
    visual_identity: VisualIdentity
