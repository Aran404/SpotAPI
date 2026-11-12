"""Library entries and saved tracks, including unavailable items."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from spotapi._parsing import integer, mapping, records
from spotapi.models.catalogue import Track, from_dict
from spotapi.types import BaseClientError


def added_time(value: object) -> datetime | None:
    """Parse Spotify's ISO timestamp, preserving its timezone when present."""
    text = mapping(value).get("isoString")
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except (TypeError, ValueError) as error:
        raise BaseClientError("Spotify returned an invalid library timestamp") from error


def track_from_data(data: Mapping[str, Any], uri: str | None = None) -> Track:
    """Normalize URI-derived IDs and tolerate absent optional album metadata."""
    uri = uri or data.get("uri")
    if not isinstance(uri, str) or not uri.startswith("spotify:track:"):
        raise BaseClientError("Spotify returned a track without a URI")
    value = {**data, "uri": uri, "id": uri.rsplit(":", 1)[-1]}
    album = mapping(data.get("albumOfTrack"))
    if "albumOfTrack" in data:
        value["albumOfTrack"] = (
            {**album, "id": album["uri"].rsplit(":", 1)[-1]}
            if isinstance(album.get("uri"), str) and isinstance(album.get("name"), str)
            else None
        )
    return from_dict(Track, value)


@dataclass(frozen=True, slots=True)
class SavedTrack:
    """A saved track record preserving its URI and optional addition timestamp.

    ``track`` is None for unavailable content. Keep the record rather than
    assuming every saved URI has playable metadata.
    """

    uri: str
    added_at: datetime | None
    track: Track | None

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> SavedTrack:
        """Parse a library record while preserving Spotify's identity and availability."""
        wrapper = mapping(row.get("track"))
        data = mapping(wrapper.get("data"))
        uri = str(wrapper.get("_uri") or wrapper.get("uri") or data.get("uri") or "")
        track = None
        if data.get("name") and uri:
            track = track_from_data(data, uri)
        return cls(uri, added_time(row.get("addedAt")), track)


@dataclass(frozen=True, slots=True)
class LibraryOption:
    """A server-supplied filter or sort ID and its display label.

    Pass the ID back to library queries; labels are presentation text.
    """

    id: str
    name: str


@dataclass(frozen=True, slots=True)
class LibraryItem:
    """A saved resource or folder in a library listing.

    ``kind`` identifies the returned resource type; ``depth`` describes folder
    nesting. The row retains library ordering and dates without performing
    a separate resource-detail lookup.
    """

    uri: str
    name: str
    kind: str
    added_at: datetime | None
    played_at: datetime | None
    pinned: bool
    pinnable: bool
    depth: int

    @classmethod
    def from_dict(cls, row: Mapping[str, Any]) -> LibraryItem:
        """Parse a library record while preserving Spotify's identity and availability."""
        wrapper = mapping(row.get("item"))
        data = mapping(wrapper.get("data"))
        uri = str(wrapper.get("_uri") or data.get("uri") or data.get("folderUri") or "")
        return cls(
            uri,
            str(data.get("name") or mapping(data.get("profile")).get("name") or ""),
            uri.split(":")[1] if ":" in uri else str(data.get("__typename", "")),
            added_time(row.get("addedAt")),
            added_time(row.get("playedAt")),
            row.get("pinned") is True,
            row.get("pinnable") is True,
            integer(row.get("depth")),
        )


@dataclass(frozen=True, slots=True)
class LibraryPage:
    """One library page with its total, paging values and available options.

    ``filters`` and ``sort_orders`` contain native IDs for later requests.
    Items can include folders and several resource kinds; use resource lookups
    when detailed track or album metadata is needed.
    """

    items: tuple[LibraryItem, ...]
    total: int
    offset: int
    limit: int
    filters: tuple[LibraryOption, ...]
    sort_orders: tuple[LibraryOption, ...]

    @classmethod
    def from_dict(cls, page: Mapping[str, Any]) -> LibraryPage:
        """Parse a library record while preserving Spotify's identity and availability."""
        if not isinstance(page.get("items"), list):
            raise BaseClientError("Spotify returned no library items")
        paging = mapping(page.get("pagingInfo"))
        return cls(
            tuple(LibraryItem.from_dict(row) for row in records(page["items"])),
            integer(page.get("totalCount")),
            integer(paging.get("offset")),
            integer(paging.get("limit")),
            tuple(
                LibraryOption(str(row["id"]), str(row["name"]))
                for row in records(page.get("availableFilters"))
            ),
            tuple(
                LibraryOption(str(row["id"]), str(row["name"]))
                for row in records(page.get("availableSortOrders"))
            ),
        )
