"""Typed search results grouped by category."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias, cast

from spotapi.operations import SEARCH_RESULT_FIELDS, SearchKind, normalize_search_kind

from .catalogue import (
    Album,
    Artist,
    Audiobook,
    Author,
    Episode,
    Genre,
    Playlist,
    Podcast,
    Track,
    User,
)

SearchEntity: TypeAlias = (
    Track | Album | Artist | Playlist | Podcast | Audiobook | Episode | User | Author | Genre
)


@dataclass(slots=True, frozen=True)
class SearchResults:
    """Typed search hits grouped by category in Spotify's returned order.

    Unrequested or empty categories contain empty tuples. ``requested_types``
    records the normalized request; ``len(results)`` counts returned hits across
    categories, not Spotify's total matches. Index with a singular or plural
    category name, such as ``results["tracks"]``, or use the typed attributes.
    """

    query: str
    requested_types: tuple[SearchKind, ...]
    tracks: tuple[Track, ...] = ()
    albums: tuple[Album, ...] = ()
    artists: tuple[Artist, ...] = ()
    playlists: tuple[Playlist, ...] = ()
    podcasts: tuple[Podcast, ...] = ()
    audiobooks: tuple[Audiobook, ...] = ()
    episodes: tuple[Episode, ...] = ()
    authors: tuple[Author, ...] = ()
    genres: tuple[Genre, ...] = ()
    users: tuple[User, ...] = ()

    def __getitem__(self, kind: str) -> tuple[SearchEntity, ...]:
        """Return results by singular, plural, or legacy entity name."""
        normalized = normalize_search_kind(kind)
        field_name = SEARCH_RESULT_FIELDS[normalized]

        return cast(tuple[SearchEntity, ...], getattr(self, field_name))

    def __bool__(self) -> bool:
        """Return whether at least one category contains a result."""
        return any(
            (
                self.tracks,
                self.albums,
                self.artists,
                self.playlists,
                self.podcasts,
                self.audiobooks,
                self.episodes,
                self.authors,
                self.genres,
                self.users,
            )
        )

    def __len__(self) -> int:
        """Return the total number of hits across all requested categories."""
        return sum(
            len(items)
            for items in (
                self.tracks,
                self.albums,
                self.artists,
                self.playlists,
                self.podcasts,
                self.audiobooks,
                self.episodes,
                self.authors,
                self.genres,
                self.users,
            )
        )
