"""Public catalogue entities beyond music search."""

from __future__ import annotations

from dataclasses import dataclass, field

from .album_details import ReleaseDate
from .common import CoverArt
from .podcast import Publisher
from .podcast_episode import EpisodePodcastReference
from .track import Duration

__all__ = (
    "Audiobook",
    "AudiobookChapter",
    "Author",
    "Episode",
    "Genre",
    "PodcastDetails",
    "PublicProfile",
    "User",
)


@dataclass(slots=True)
class Author:
    """An audiobook author's display name and Spotify URI."""

    name: str
    uri: str

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]


@dataclass(slots=True)
class Audiobook:
    """Audiobook metadata with optional authors, artwork and duration.

    Spotify show links can identify audiobooks. Chapters are retrieved through
    the catalogue's explicit chapter iterator, not by reading this object.
    """

    name: str
    uri: str
    authors_v2: list[Author] = field(default_factory=list[Author])
    description: str | None = None
    cover_art: CoverArt | None = None
    audiobook_duration: Duration | None = None

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]

    def __repr__(self) -> str:
        return f"<Audiobook name={self.name!r} uri={self.uri!r}>"


@dataclass(slots=True)
class AudiobookChapter:
    """A chapter returned by an audiobook's chapter list."""

    id: str
    uri: str
    name: str
    description: str | None = None
    duration: Duration | None = None
    cover_art: CoverArt | None = None


@dataclass(slots=True)
class Episode:
    """A lightweight episode search result with optional podcast metadata.

    Use an explicit episode lookup for the richer PodcastEpisodeDetails model.
    Duration and release metadata can be absent in search previews.
    """

    name: str
    uri: str
    description: str | None = None
    duration: Duration | None = None
    cover_art: CoverArt | None = None
    release_date: ReleaseDate | None = None
    podcast_v2: EpisodePodcastReference | None = None

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]

    def __repr__(self) -> str:
        return f"<Episode name={self.name!r} uri={self.uri!r}>"


@dataclass(slots=True)
class Genre:
    """A search category with a display name, URI and optional image.

    A genre URI is not a playable track or a directly supported resource lookup.
    """

    name: str
    uri: str
    image: CoverArt | None = None


@dataclass(slots=True)
class User:
    """A lightweight user search result with optional username and avatar.

    ``name`` exposes ``display_name`` consistently with other search entities.
    Use an explicit profile lookup for follower and public-playlist metadata.
    """

    display_name: str
    uri: str
    username: str | None = None
    avatar: CoverArt | None = None

    @property
    def name(self) -> str:
        """Return the display name from the resource's profile metadata."""
        return self.display_name

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]


@dataclass(slots=True)
class ProfilePlaylist:
    """A public playlist reference with optional owner and follower metadata."""

    name: str
    uri: str
    followers_count: int | None = None
    owner_name: str | None = None
    owner_uri: str | None = None
    image_url: str | None = None
    is_following: bool | None = None


@dataclass(slots=True)
class PublicProfile:
    """A public user profile and its first supplied public-playlist references.

    Follower counts and privacy-related fields may be absent. The embedded
    playlist collection is a preview, not an implicitly paginated export.
    """

    name: str
    uri: str
    image_url: str | None = None
    followers_count: int | None = None
    following_count: int | None = None
    total_public_playlists_count: int | None = None
    public_playlists: list[ProfilePlaylist] = field(default_factory=list[ProfilePlaylist])
    is_verified: bool | None = None
    is_current_user: bool | None = None
    allow_follows: bool | None = None
    show_follows: bool | None = None
    color: int | None = None

    def __repr__(self) -> str:
        return f"<PublicProfile name={self.name!r} followers={self.followers_count!r}>"


@dataclass(slots=True)
class PodcastDetails:
    """Podcast metadata without an implicitly fetched episode collection.

    Read episodes through the catalogue iterator. Optional artwork, publisher
    and media fields remain unknown when Spotify omits them.
    """

    name: str
    uri: str
    description: str | None = None
    cover_art: CoverArt | None = None
    publisher: Publisher | None = None
    media_type: str | None = None

    @property
    def id(self) -> str:
        """Return the Spotify identifier derived from this resource URI."""
        return self.uri.rsplit(":", 1)[-1]

    def __repr__(self) -> str:
        return f"<PodcastDetails name={self.name!r} uri={self.uri!r}>"
