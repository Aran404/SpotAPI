"""Bounded downloads of artwork, published preview clips and Canvas assets."""

from __future__ import annotations

import asyncio
import importlib
import tempfile
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, cast
from urllib.parse import urlsplit

import wreq

from .connection import HTTPClient
from .connection.http import response_headers
from .embeds import Embed
from .models.discovery import Canvas
from .types import BaseClientError, HTTPError


def _media_url(url: str) -> None:
    parsed = urlsplit(url)
    host = (parsed.hostname or "").casefold()
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or not any(
            host == domain or host.endswith("." + domain)
            for domain in ("scdn.co", "spotifycdn.com", "spotifycdn.net")
        )
    ):
        raise ValueError("Use an HTTPS Spotify media CDN URL")


class Media:
    """Download returned public assets using an isolated unauthenticated transport.

    No bearer headers are sent and redirects are disabled. Each download is
    bounded by max_bytes, including responses with no Content-Length. Existing
    output files are never overwritten. This does not download full tracks.
    """

    __slots__ = ("max_bytes",)

    def __init__(self, *, max_bytes: int = 32 * 1024 * 1024) -> None:
        if type(max_bytes) is not int or max_bytes < 1:
            raise ValueError("max_bytes must be a positive integer")
        self.max_bytes = max_bytes

    async def _download(self, url: str, destination: Path, media_type: str) -> Path:
        _media_url(url)
        async with (
            HTTPClient() as http,
            http.stream("GET", url, redirect=wreq.redirect.Policy.none()) as response,
        ):
            if not response.status.is_success():
                raise HTTPError("Media download failed", status_code=response.status.as_int())
            headers = response_headers(response)
            if not headers.get("content-type", "").casefold().startswith(media_type):
                raise BaseClientError("Spotify returned an unexpected media type")
            if response.content_length is not None and response.content_length > self.max_bytes:
                raise BaseClientError("Spotify media exceeds max_bytes")
            data = bytearray()
            # wreq 0.12 incorrectly marks __aiter__ async; it returns the native iterator itself.
            async with response.stream() as stream:
                async for chunk in cast(AsyncIterator[bytes | wreq.HeaderMap], stream):
                    if not isinstance(chunk, bytes):
                        continue
                    if len(data) + len(chunk) > self.max_bytes:
                        raise BaseClientError("Spotify media exceeds max_bytes")
                    data.extend(chunk)

        # Bound memory before writing. Exclusive creation prevents accidental overwrites.
        def save() -> None:
            output = destination.open("xb")
            try:
                with output:
                    output.write(data)
            except BaseException:
                destination.unlink(missing_ok=True)
                raise

        await asyncio.to_thread(save)
        return destination

    async def download_cover(self, source: Embed, destination: str | Path) -> Path:
        """Save the first available artwork source; destination is an explicit file path."""
        if not source.image_urls:
            raise BaseClientError("This resource has no cover image")
        return await self._download(source.image_urls[0], Path(destination), "image/")

    async def download_preview(
        self, source: Embed, destination: str | Path, *, embed_cover: bool = False
    ) -> Path:
        """Save a published preview, optionally tagging it with cover art and title.

        Cover embedding requires spotapi[media]. A tagging failure raises and
        leaves the downloaded preview available; existing files are never
        replaced. Only the published preview URL is used, never full audio.
        """
        if source.resource.kind not in {"track", "episode"} or not source.preview_url:
            raise BaseClientError("This resource has no published audio preview")
        id3: Any = None
        if embed_cover:
            try:
                id3 = importlib.import_module("mutagen.id3")
            except ImportError as error:
                raise RuntimeError(
                    "Install cover tagging with pip install 'spotapi[media]'"
                ) from error
            if not source.image_urls:
                raise BaseClientError("This resource has no artwork to embed")
        target = await self._download(source.preview_url, Path(destination), "audio/")
        if embed_cover:
            with tempfile.TemporaryDirectory(prefix="spotapi-cover-") as directory:
                cover = await self.download_cover(source, Path(directory) / "cover")

                def tag() -> None:
                    artwork = cover.read_bytes()
                    mime = (
                        "image/png" if artwork.startswith(b"\x89PNG\r\n\x1a\n") else "image/jpeg"
                    )
                    if mime == "image/jpeg" and not artwork.startswith(b"\xff\xd8\xff"):
                        raise BaseClientError("Preview embedding supports JPEG and PNG artwork")
                    try:
                        tags = id3.ID3(target)
                    except id3.ID3NoHeaderError:
                        tags = id3.ID3()
                    tags.add(id3.TIT2(encoding=3, text=[source.name]))
                    tags.add(id3.APIC(encoding=3, mime=mime, type=3, desc="Cover", data=artwork))
                    tags.save(target)

                await asyncio.to_thread(tag)
        return target

    async def download_canvas(self, source: Canvas, destination: str | Path) -> Path:
        """Save the Canvas asset returned by an entitled lookup."""
        return await self._download(source.url, Path(destination), "video/")
