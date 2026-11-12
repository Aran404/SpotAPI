"""Detailed Spotify podcast episode models for ``getEpisodeOrChapter``."""

from __future__ import annotations

from dataclasses import dataclass, field

from .album_details import ReleaseDate
from .common import Sources, VisualIdentity
from .track import ContentRating, Duration
from .track_details import SharingInfo

__all__ = ("PodcastEpisodeDetails",)


@dataclass(slots=True)
class EpisodeAudioSource:
    url: str


@dataclass(slots=True)
class EpisodeAudio:
    items: list[EpisodeAudioSource] = field(default_factory=list[EpisodeAudioSource])


@dataclass(slots=True)
class EpisodeCoverArt:
    """Episode artwork without extracted color metadata."""

    sources: list[Sources] = field(default_factory=list[Sources])


@dataclass(slots=True)
class EpisodePlayability:
    playable: bool
    reason: str | None = None
    unplayability_reasons: list[str] = field(default_factory=list[str])


@dataclass(slots=True)
class EpisodePlayedState:
    play_position_milliseconds: int | None = None
    state: str | None = None


@dataclass(slots=True)
class EpisodePodcast:
    """Podcast information embedded in an episode lookup."""

    name: str
    uri: str
    cover_art: EpisodeCoverArt | None = None
    show_types: list[object] = field(default_factory=list[object])
    access_info: object | None = None
    trailer_v2: object | None = None


@dataclass(slots=True)
class EpisodePodcastReference:
    data: EpisodePodcast | None = None


@dataclass(slots=True)
class EpisodeAudioPreview:
    cdn_url: str


@dataclass(slots=True)
class EpisodePreviewPlayback:
    audio_preview: EpisodeAudioPreview | None = None


@dataclass(slots=True)
class EpisodeRestrictions:
    paywall_content: bool | None = None


@dataclass(slots=True)
class EpisodeTranscripts:
    items: list[object] = field(default_factory=list[object])


@dataclass(slots=True)
class PodcastEpisodeDetails:
    """A Spotify podcast episode returned by a direct URI lookup.

    Attributes:
        id (str): Spotify episode ID.
        name (str): Episode title.
        uri (str): Spotify episode URI.
        type (str): Spotify content type, typically "PODCAST_EPISODE".
        duration (Duration | None): Episode duration in milliseconds.
        podcast_v2 (EpisodePodcastReference | None): Podcast containing this episode.
        release_date (ReleaseDate | None): Original publication date and precision.
        played_state (EpisodePlayedState | None): Playback progress for the current user.
        playability (EpisodePlayability | None): Current playback availability.
        audio (EpisodeAudio | None): Available audio sources.
        preview_playback (EpisodePreviewPlayback | None): Audio preview metadata.
    """

    id: str
    name: str
    uri: str
    type: str

    audio: EpisodeAudio | None = None
    content_rating: ContentRating | None = None
    content_ratings_v2: object | None = None
    cover_art: EpisodeCoverArt | None = None
    description: str | None = None
    duration: Duration | None = None
    html_description: str | None = None
    media_types: list[str] = field(default_factory=list[str])
    playability: EpisodePlayability | None = None
    played_state: EpisodePlayedState | None = None
    podcast_v2: EpisodePodcastReference | None = None
    preview_playback: EpisodePreviewPlayback | None = None
    release_date: ReleaseDate | None = None
    restrictions: EpisodeRestrictions | None = None
    sharing_info: SharingInfo | None = None
    transcripts: EpisodeTranscripts | None = None
    visual_identity: VisualIdentity | None = None

    access_info: object | None = None
    content_information: object | None = None
    contents: list[object] = field(default_factory=list[object])
    creator: object | None = None
    gated_entity_relations: list[object] = field(default_factory=list[object])
    segments: object | None = None

    @property
    def podcast(self) -> EpisodePodcast | None:
        """The containing podcast, without the data wrapper."""
        return self.podcast_v2.data if self.podcast_v2 else None

    def __repr__(self) -> str:
        return f"<PodcastEpisodeDetails id={self.id!r} name={self.name!r}>"
