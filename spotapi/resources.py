"""Normalize Spotify links and identifiers without opening a client."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote, urlsplit

from .operations import ResourceInputKind, ResourceKind, normalize_resource_kind

__all__ = ("SpotifyResource", "parse_spotify_resource")


@dataclass(slots=True, frozen=True)
class SpotifyResource:
    """A validated Spotify identity with its kind, ID, URI and canonical share URL.

    Construct through ``parse_spotify_resource`` to normalize aliases and strip
    tracking parameters. Parsing performs no network requests; short links must
    first be expanded by the caller.
    """

    kind: ResourceKind
    id: str
    uri: str
    url: str


def parse_spotify_resource(
    value: str,
    kind: ResourceInputKind | None = None,
) -> SpotifyResource:
    """Parse and validate a Spotify URL, URI, or ID."""
    value = value.strip()

    if not value:
        raise ValueError("Spotify resource must not be empty")

    parsed_kind: str
    resource_id: str

    if value.startswith("spotify:"):
        parts = value.split(":")

        if len(parts) == 3:
            _, parsed_kind, resource_id = parts
        elif len(parts) == 5 and parts[1] == "user" and parts[3] == "playlist":
            # Legacy user playlist URI: spotify:user:<user>:playlist:<id>.
            parsed_kind, resource_id = "playlist", parts[4]
        else:
            raise ValueError(f"Unsupported Spotify URI: {value!r}")
    else:
        try:
            parsed = urlsplit(value)
        except ValueError as exc:
            raise ValueError(f"Invalid Spotify URL: {value!r}") from exc

        if parsed.scheme in {"http", "https"}:
            hostname = (parsed.hostname or "").casefold()

            if hostname not in {"open.spotify.com", "www.open.spotify.com"}:
                if hostname in {"spotify.link", "www.spotify.link", "spoti.fi"}:
                    raise ValueError("Expand Spotify short links to an open.spotify.com URL")

                raise ValueError("Expected a URL on open.spotify.com")

            segments = [unquote(part) for part in parsed.path.split("/") if part]

            if segments and segments[0].startswith("intl-"):
                segments.pop(0)

            if segments and segments[0] in {"embed", "embed-podcast"}:
                segments.pop(0)

            # Legacy profile playlist path: /user/<username>/playlist/<id>.
            if len(segments) >= 4 and segments[0] == "user" and segments[2] == "playlist":
                parsed_kind, resource_id = "playlist", segments[3]
            elif len(segments) >= 2:
                parsed_kind, resource_id = segments[0], segments[1]
            else:
                raise ValueError(f"URL does not identify a Spotify resource: {value!r}")
        elif parsed.scheme or "://" in value:
            raise ValueError("Expected a Spotify URI or URL on open.spotify.com")
        else:
            if kind is None:
                raise ValueError(
                    "A bare Spotify ID is ambiguous; pass kind='track', 'album', etc."
                )

            parsed_kind, resource_id = kind, value

    canonical_kind = normalize_resource_kind(parsed_kind)

    if kind is not None and normalize_resource_kind(kind) != canonical_kind:
        raise ValueError(f"Resource is a {canonical_kind}, but kind={kind!r} was requested")

    if (
        not resource_id
        or len(resource_id) > 128
        or any(character.isspace() or character in "/?:#" for character in resource_id)
    ):
        raise ValueError(f"Invalid Spotify resource ID: {resource_id!r}")

    normalized_uri = f"spotify:{canonical_kind}:{resource_id}"
    normalized_url = f"https://open.spotify.com/{canonical_kind}/{quote(resource_id, safe='')}"

    return SpotifyResource(
        kind=canonical_kind,
        id=resource_id,
        uri=normalized_uri,
        url=normalized_url,
    )
