"""Resolve display metadata for the limited queue Spotify actually reports."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from dataclasses import replace
from typing import TYPE_CHECKING

from spotapi.models import PlaybackTrack

if TYPE_CHECKING:
    from spotapi.catalogue import Catalogue


class QueuePreview:
    """Bounded title/artist cache; never infer Spotify's next playback choice."""

    def __init__(self, catalogue: Catalogue, *, cache_size: int = 64) -> None:
        self.catalogue = catalogue
        self._cache: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self.cache_size = cache_size

    async def enrich(self, tracks: tuple[PlaybackTrack, ...]) -> tuple[PlaybackTrack, ...]:
        """Fill missing titles without changing snapshot order or queue identity."""
        # Resolve each URI once, even if it occurs multiple times in the queue.
        unknown = {
            item.uri
            for item in tracks[:8]
            if not (item.name and item.artist)
            and item.uri.startswith("spotify:track:")
            and item.uri not in self._cache
        }
        await asyncio.gather(*(self._resolve(uri) for uri in unknown))

        results: list[PlaybackTrack] = []
        for item in tracks[:8]:
            metadata = self._cache.get(item.uri)
            if metadata:
                self._cache.move_to_end(item.uri)
                results.append(
                    replace(item, name=item.name or metadata[0], artist=item.artist or metadata[1])
                )
            else:
                results.append(item)
        return tuple(results)

    async def _resolve(self, uri: str) -> None:
        try:
            track = await self.catalogue.get_track(uri)
            first = track.first_artist.items if track.first_artist else ()
            others = track.other_artists.items if track.other_artists else ()
            artists = ", ".join(
                artist.profile.name for artist in (*first, *others) if artist.profile
            )
            name = track.name
        except Exception:
            # Metadata is optional. The underlying occurrence remains visible.
            return
        self._cache[uri] = (name, artists)
        while len(self._cache) > self.cache_size:
            self._cache.popitem(last=False)
