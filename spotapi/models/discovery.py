"""Recommendation and Canvas models shared by public and authenticated reads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from spotapi._parsing import mapping, records
from spotapi._protocol.protobuf import ProtoMessage
from spotapi.models.catalogue import Track, from_dict
from spotapi.types import BaseClientError


@dataclass(slots=True)
class RecommendedTrack(Track):
    """A recommended track with optional ranking score and popularity.

    Recommendation metadata is retained when supplied; absent ranking values
    are not synthesized.
    """

    score: float | None = None
    popularity: int | None = None


def recommended_tracks(body: Mapping[str, Any]) -> tuple[RecommendedTrack, ...]:
    """Parse recommendation metadata, retaining optional scores and missing artwork."""
    if not isinstance(body.get("recommendedTracks"), list):
        raise BaseClientError("Spotify returned no playlist recommendations")
    tracks: list[RecommendedTrack] = []
    for row in records(body["recommendedTracks"]):
        if (
            not isinstance(row.get("id"), str)
            or not row["id"]
            or not isinstance(row.get("name"), str)
        ):
            raise BaseClientError("Spotify returned an incomplete recommended track")
        album = mapping(row.get("album"))
        image_url = album.get("largeImageUrl") or album.get("imageUrl")
        payload = {
            "id": row["id"],
            "uri": "spotify:track:" + str(row["id"]),
            "name": row["name"],
            "duration": {"totalMilliseconds": row.get("duration", 0)},
            "contentRating": {"label": "EXPLICIT" if row.get("explicit") else "NONE"},
            "artists": {
                "items": [
                    {
                        "uri": "spotify:artist:" + str(artist["id"]),
                        "profile": {"name": artist["name"]},
                    }
                    for artist in records(row.get("artists"))
                    if isinstance(artist.get("id"), str) and isinstance(artist.get("name"), str)
                ]
            },
            "albumOfTrack": (
                {
                    "id": album.get("id", ""),
                    "uri": "spotify:album:" + str(album.get("id", "")),
                    "name": album.get("name", ""),
                    "coverArt": {
                        "sources": (
                            [
                                {
                                    "url": image_url,
                                    "width": 640,
                                    "height": 640,
                                }
                            ]
                            if image_url
                            else []
                        )
                    },
                }
                if album.get("id") and album.get("name")
                else None
            ),
            "score": row.get("score"),
            "popularity": row.get("popularity"),
        }
        tracks.append(from_dict(RecommendedTrack, payload))
    return tuple(tracks)


@dataclass(frozen=True, slots=True)
class Canvas:
    """Available Canvas metadata, including the media URL and credited artist.

    The model describes the returned asset; constructing or reading it does
    not download the video.
    """

    id: str
    uri: str
    url: str
    track_uri: str
    artist_uri: str | None = None
    artist_name: str | None = None
    artist_image_url: str | None = None

    @classmethod
    def from_message(cls, message: ProtoMessage) -> Canvas:
        """Decode known Canvas and credited-artist fields from a protobuf record."""
        artists = message.messages(6)
        artist = artists[0] if artists else ProtoMessage({})
        return cls(
            message.string(1),
            message.string(11),
            message.string(2),
            message.string(5),
            artist.string(1) or None,
            artist.string(2) or None,
            artist.string(3) or None,
        )


@dataclass(frozen=True, slots=True)
class CoverColors:
    """Spotify's raw, dark and light artwork colors as CSS hex strings."""

    raw: str
    dark: str
    light: str
    is_fallback: bool | None = None

    @classmethod
    def from_dict(cls, body: Mapping[str, Any]) -> CoverColors:
        """Decode the first requested image's extracted palette."""
        entries: Any = body.get("extractedColors")
        if not isinstance(entries, list) or len(cast(list[object], entries)) != 1:
            raise BaseClientError("Spotify returned no unique image palette")
        entry = mapping(cast(list[object], entries)[0])
        values: list[str] = []
        for name in ("colorRaw", "colorDark", "colorLight"):
            value = mapping(entry.get(name)).get("hex")
            if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
                raise BaseClientError("Spotify returned an invalid palette color")
            try:
                int(value[1:], 16)
            except ValueError as error:
                raise BaseClientError("Spotify returned an invalid palette color") from error
            values.append(value)
        fallback = mapping(entry.get("colorRaw")).get("isFallback")
        return cls(*values, is_fallback=fallback if isinstance(fallback, bool) else None)


@dataclass(frozen=True, slots=True)
class ConcertArtist:
    """A billed artist, with an identity only when Spotify supplies one."""

    name: str
    uri: str | None = None


@dataclass(frozen=True, slots=True)
class Concert:
    """An upcoming event; date is Spotify's unmodified ISO string.

    Listings can vary by region. A missing city/date is not inferred from the
    caller's location. This is metadata, not a ticket reservation.
    """

    uri: str
    title: str
    start_date: str | None = None
    city: str | None = None
    artists: tuple[ConcertArtist, ...] = ()

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> Concert:
        """Decode a concert record and validate its identity and display title."""
        uri, title = value.get("uri"), value.get("title")
        if (
            not isinstance(uri, str)
            or not uri.startswith("spotify:concert:")
            or not isinstance(title, str)
            or not title
        ):
            raise BaseClientError("Spotify returned an invalid concert")
        artists: list[ConcertArtist] = []
        for item in records(mapping(value.get("artists")).get("items")):
            artist = mapping(item.get("data"))
            name = mapping(artist.get("profile")).get("name")
            if isinstance(name, str) and name:
                artists.append(
                    ConcertArtist(
                        name, artist.get("uri") if isinstance(artist.get("uri"), str) else None
                    )
                )
        city = mapping(value.get("location")).get("city")
        start = value.get("startDateIsoString")
        return cls(
            uri,
            title,
            start if isinstance(start, str) else None,
            city if isinstance(city, str) else None,
            tuple(artists),
        )


@dataclass(frozen=True, slots=True)
class Chart:
    """An editorial playlist shortcut, not a separate chart-data API."""

    key: str
    name: str
    playlist_id: str

    @property
    def uri(self) -> str:
        """The backing playlist URI, usable with ordinary playlist pagination."""
        return f"spotify:playlist:{self.playlist_id}"
