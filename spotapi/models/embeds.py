"""Sparse public embed results, distinct from rich catalogue detail models."""

from __future__ import annotations

from dataclasses import dataclass

from spotapi._parsing import integer, mapping, records
from spotapi._protocol.embeds import entity_from_html
from spotapi.resources import SpotifyResource
from spotapi.types import BaseClientError


@dataclass(frozen=True, slots=True)
class Embed:
    """A public embed snapshot with optional preview and artwork URLs.

    This deliberately differs from a rich catalogue detail model: absent play
    counts, availability and other Pathfinder-only fields are not fabricated.
    Only the entity is retained; embed-page tokens are discarded.
    """

    resource: SpotifyResource
    name: str
    duration_ms: int | None
    preview_url: str | None
    image_urls: tuple[str, ...]

    @classmethod
    def from_html(cls, source: str, resource: SpotifyResource) -> Embed:
        """Extract the entity from an embed page and verify its requested identity."""
        entity = entity_from_html(source, resource.uri)
        name = entity.get("name") or entity.get("title")
        if not isinstance(name, str) or not name:
            raise BaseClientError("Spotify embed page returned no title")
        preview = mapping(entity.get("audioPreview")).get("url")
        images = records(mapping(entity.get("visualIdentity")).get("image"))
        duration = integer(entity.get("duration"), -1)
        return cls(
            resource,
            name,
            duration if duration >= 0 else None,
            preview if isinstance(preview, str) else None,
            tuple(image["url"] for image in images if isinstance(image.get("url"), str)),
        )
