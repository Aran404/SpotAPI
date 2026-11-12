"""Bounded pages of public playlist previews."""

from __future__ import annotations

from dataclasses import dataclass

from spotapi.models.catalogue.entities import ProfilePlaylist


@dataclass(frozen=True, slots=True)
class ProfilePlaylists:
    """A bounded public-playlist page with its total, offset and requested limit.

    Use the profile helper's page iterator to read subsequent pages.
    """

    items: tuple[ProfilePlaylist, ...]
    total: int
    offset: int
    limit: int
