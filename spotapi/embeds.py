"""Public embed metadata and preview clips without a Pathfinder dependency."""

from __future__ import annotations

from typing import Any

from .client import AsyncClient
from .models.embeds import Embed
from .resources import SpotifyResource, parse_spotify_resource


async def get_embed(
    value: str, *, kind: str | None = None, browser: bool = False, proxy: str | None = None
) -> Embed:
    """Read a public Spotify URL/URI through its embed page, without login.

    This explicit alternative remains usable when persisted queries change.
    Bare IDs require a kind. It does not silently downgrade rich detail results.
    """
    # The parser accepts the public resource aliases and validates unsupported kinds.
    resource = parse_spotify_resource(value) if kind is None else _typed_resource(value, kind)
    if resource.kind not in {"track", "album", "artist", "playlist", "show", "episode"}:
        raise ValueError("This resource has no supported public embed")
    url = f"https://open.spotify.com/embed/{resource.kind}/{resource.id}"
    if browser:
        if proxy is not None:
            raise ValueError("Use HTTP embed reads when configuring a proxy")
        import importlib

        try:
            module: Any = importlib.import_module("playwright.async_api")
        except ImportError as error:
            raise RuntimeError(
                "Install spotapi[browser] and playwright install chromium"
            ) from error
        async with module.async_playwright() as playwright:
            instance = await playwright.chromium.launch(headless=True)
            try:
                page = await instance.new_page()
                await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                return Embed.from_html(await page.content(), resource)
            finally:
                await instance.close()
    async with AsyncClient(proxy=proxy) as client:
        response = await client.get(
            url,
            headers={"accept": "text/html"},
        )
    return Embed.from_html(response.text, resource)


def _typed_resource(value: str, kind: str) -> SpotifyResource:
    from .operations import normalize_resource_kind

    return parse_spotify_resource(value, normalize_resource_kind(kind))
