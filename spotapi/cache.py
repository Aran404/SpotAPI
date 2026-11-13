"""Opt-in bounded caching for anonymous public catalogue responses."""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import threading
import time
from collections import OrderedDict
from collections.abc import Mapping
from contextlib import suppress
from pathlib import Path
from typing import Any, cast

from .datastruct import ObjectDict
from .operations import Operations
from .queries import Queries
from .query import SharedQueryClient

_PUBLIC_OPERATIONS = frozenset(
    {
        Operations.GET_TRACK,
        Operations.GET_ALBUM,
        Operations.QUERY_ARTIST_OVERVIEW,
        Operations.GET_EPISODE_OR_CHAPTER,
        Operations.QUERY_SHOW_METADATA_V2,
        Operations.QUERY_PODCAST_EPISODES,
        Operations.QUERY_ALBUM_TRACKS,
        Operations.SEARCH_DESKTOP,
        Operations.QUERY_ARTIST_RELATED,
        Operations.SIMILAR_ALBUMS_BASED_ON_THIS_TRACK,
        Operations.ARTIST_CONCERTS,
        Operations.FETCH_EXTRACTED_COLORS,
    }
)


class ResponseCache:
    """Bound public metadata in memory, optionally persisting it to a directory.

    Args:
        directory: Optional on-disk store. No embed HTML, cookies or headers
            are cached. Catalogue rejects this cache for authenticated scopes.
        ttl: Lifetime in seconds, default one day. Cached data can be stale.
        max_entries: Maximum retained memory entries.
        max_bytes: Maximum JSON size of an individual response.

    Cache corruption and I/O errors are misses, never successful empty results.
    Disk storage is explicitly caller-managed; clear its directory when no
    longer needed. Memory LRU eviction does not delete shared disk entries.
    """

    def __init__(
        self,
        directory: str | Path | None = None,
        *,
        ttl: float = 86400,
        max_entries: int = 128,
        max_bytes: int = 1024 * 1024,
    ) -> None:
        if isinstance(ttl, bool) or not math.isfinite(ttl) or ttl <= 0:
            raise ValueError("ttl must be finite and positive")
        if (
            type(max_entries) is not int
            or max_entries < 1
            or type(max_bytes) is not int
            or max_bytes < 1
        ):
            raise ValueError("Cache bounds must be positive integers")
        self.directory = Path(directory) if directory is not None else None
        self.ttl, self.max_entries, self.max_bytes = ttl, max_entries, max_bytes
        self._memory: OrderedDict[str, str] = OrderedDict()
        self._lock = threading.Lock()

    @staticmethod
    def _validate_key(key: str) -> None:
        if len(key) != 64 or any(char not in "0123456789abcdef" for char in key):
            raise ValueError("Cache keys must be SHA-256 hex digests")

    def key(self, operation: str, variables: Mapping[str, Any], namespace: str) -> str:
        source = json.dumps(
            [namespace, operation, variables], sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(source.encode()).hexdigest()

    def get(self, key: str) -> ObjectDict | None:
        self._validate_key(key)
        with self._lock:
            encoded = self._memory.get(key)
            if encoded is not None:
                self._memory.move_to_end(key)
        try:
            if encoded is None and self.directory is not None:
                with (self.directory / (key + ".json")).open(encoding="utf-8") as source:
                    encoded = source.read(self.max_bytes + 1025)
            if encoded is None or len(encoded.encode()) > self.max_bytes + 1024:
                return None
            envelope: Any = json.loads(encoded)
            if (
                not isinstance(envelope, dict)
                or cast(dict[str, Any], envelope).get("version") != 1
            ):
                return None
            document = cast(dict[str, Any], envelope)
            expires: object = document.get("expires")
            if (
                isinstance(expires, bool)
                or not isinstance(expires, (int, float))
                or not math.isfinite(expires)
                or expires <= time.time()
                or expires > time.time() + self.ttl + 1
            ):
                return None
            payload: Any = document.get("data")
            return ObjectDict(cast(dict[str, Any], payload)) if isinstance(payload, dict) else None
        except (OSError, ValueError, TypeError, RecursionError):
            return None

    def put(self, key: str, data: ObjectDict) -> None:
        self._validate_key(key)
        try:
            payload = json.dumps(data.to_dict(), allow_nan=False, separators=(",", ":"))
        except (TypeError, ValueError):
            return
        if len(payload.encode()) > self.max_bytes:
            return
        encoded = (
            '{"version":1,"expires":' + str(time.time() + self.ttl) + ',"data":' + payload + "}"
        )
        with self._lock:
            self._memory[key] = encoded
            self._memory.move_to_end(key)
            while len(self._memory) > self.max_entries:
                self._memory.popitem(last=False)
        if self.directory is not None:
            temporary: str | None = None
            try:
                self.directory.mkdir(parents=True, exist_ok=True)
                fd, temporary = tempfile.mkstemp(
                    dir=self.directory, prefix=".spotapi-", suffix=".tmp"
                )
                with os.fdopen(fd, "w", encoding="utf-8") as target:
                    target.write(encoded)
                os.replace(temporary, self.directory / (key + ".json"))
            except OSError:
                pass
            finally:
                if temporary is not None:
                    with suppress(OSError):
                        Path(temporary).unlink(missing_ok=True)


class CachedQueries(Queries):
    def __init__(self, pool: SharedQueryClient, cache: ResponseCache, namespace: str) -> None:
        super().__init__(pool)
        self._cache = cache
        self._namespace = namespace

    async def query(self, operation: str, variables: Mapping[str, Any]) -> ObjectDict:
        if operation not in _PUBLIC_OPERATIONS:
            return await super().query(operation, variables)
        import asyncio

        key = self._cache.key(operation, variables, self._namespace)
        cached = await asyncio.to_thread(self._cache.get, key)
        if cached is not None:
            return cached
        result = await super().query(operation, variables)
        await asyncio.to_thread(self._cache.put, key, result)
        return result
