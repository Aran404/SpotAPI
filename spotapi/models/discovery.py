"""Recommendation and Canvas models shared by public and authenticated reads."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

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
