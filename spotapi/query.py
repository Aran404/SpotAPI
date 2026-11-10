"""Authenticated transport for Spotify's persisted GraphQL queries.

``query_client_pool()`` returns a shared owner of one ``QueryClient``
for the running event loop. Initialization is lazy; requests borrow the
same concurrent client. ``asyncio.run`` attempts routine cleanup;
framework-managed loops should use an application shutdown hook.

Example:
    Run a persisted query on the shared client::

        async with query_client_pool().acquire() as client:
            await client.pathfinder_query(variables, "searchDesktop")
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, ClassVar, Self, cast

from .client import AsyncClient
from .connection import Response
from .datastruct import ObjectDict
from .session import AuthSession, normalize_language
from .specialized.data_wrappers import Profile
from .types import BaseClientError

__all__ = (
    "QueryClient",
    "close_query_clients",
    "get_at_depth",
    "paginate",
    "query_client_pool",
)

# Only operations whose read semantics are known locally opt into POST retries.
# Unknown persisted operations may mutate state even though their URL says query.
_READ_OPERATIONS = frozenset(
    {
        "searchDesktop",
        "searchAudiobooks",
        "searchEpisodes",
        "searchAuthors",
        "searchGenres",
        "searchUsers",
        "profileAttributes",
        "userTopContent",
        "fetchLibraryTracks",
        "libraryV3",
        "areEntitiesInLibrary",
        "isFollowingUsers",
        "recents",
        "fetchPlaylistContents",
        "fetchPlaylistMetadata",
        "queryShowMetadataV2",
        "getPodcastOrBookName",
        "getEpisodeOrChapter",
        "getTrack",
        "getAlbum",
        "queryArtistOverview",
        "queryPodcastEpisodes",
        "queryAlbumTracks",
        "queryTrackCreditsGroupedModal",
        "queryArtistDiscographyAll",
        "queryArtistDiscographyAlbums",
        "queryArtistDiscographySingles",
        "queryArtistDiscographyCompilations",
        "queryArtistRelated",
    }
)


def get_at_depth(data: ObjectDict, depth: int) -> ObjectDict | None:
    """Descend into the largest nested object, ``depth`` levels deep.

    At every level the child object with the most keys is followed. This
    is used to unwrap Pathfinder responses, whose payload is nested
    under operation-specific keys such as ``data.searchV2.tracksV2``.

    Args:
        data: Object to start from.
        depth: Number of levels to descend.

    Returns:
        The object found at ``depth``, or ``None`` if the structure ran
        out of nested objects before reaching it.
    """
    current = data

    for _ in range(depth):
        children = (value for value in current.values() if isinstance(value, ObjectDict))
        child = max(children, key=len, default=None)

        if child is None:
            return None

        current = child

    return current


_DEFAULT_PAGE_CAP = 1000


async def paginate(
    request: Callable[[dict[str, Any]], Awaitable[ObjectDict]],
    variables: dict[str, Any],
    *,
    obey_total_count: bool = True,
    return_raw: bool = False,
    extract_page: Callable[[ObjectDict], ObjectDict] | None = None,
) -> AsyncGenerator[ObjectDict, None]:
    """Paginate using a page fetcher that owns only its individual request.

    The fetcher releases its lease before yielding each page. By default,
    the response is unwrapped two levels; ``extract_page`` overrides this
    with a caller-chosen shape. ``return_raw`` changes only the yielded
    object, not pagination termination.
    """
    offset = variables.get("offset", 0)
    limit = variables["limit"]

    if isinstance(limit, bool) or not isinstance(limit, int) or limit <= 0:
        raise ValueError("limit must be a positive integer")

    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise ValueError("offset must be a non-negative integer")

    total_count = offset + _DEFAULT_PAGE_CAP

    while offset < total_count:
        response = await request({**variables, "offset": offset})

        # The caller may provide an extractor for a nonstandard response.
        # Otherwise retain the historical two-level Pathfinder heuristic.
        page = extract_page(response) if extract_page is not None else get_at_depth(response, 2)

        if page is None:
            page = response

        if obey_total_count:
            count = page.get("totalCount")

            if type(count) is int and count >= 0:
                total_count = count

        # Inspect the result collection even when yielding raw envelopes.
        # False/zero values in other fields do not terminate a page.
        items = page["items"] if "items" in page else page.get("_items")

        if isinstance(items, list) and not items:
            return

        yield response if return_raw else page

        # Prefer the cursor-like offset supplied by Spotify when available.
        # A response that repeats an offset must not create an infinite loop.
        raw_paging: object = page.get("pagingInfo")
        paging_info = cast(dict[str, object], raw_paging) if isinstance(raw_paging, dict) else {}
        next_offset = paging_info.get("nextOffset")

        if "nextOffset" in paging_info:
            if next_offset is None:
                return

            if type(next_offset) is int:
                if next_offset <= offset:
                    return

                offset = next_offset
                continue

        offset += limit


class QueryClient:
    """Authenticated transport for Spotify's persisted GraphQL queries.

    You rarely need to build one yourself. The owner returned from
    ``query_client_pool()`` shares one instance across concurrent requests.

    Attributes:
        session: Authorized session used to sign every request.
    """

    __slots__ = ("_profile", "_owns_session", "session")

    _QUERY_VERSION: ClassVar[int] = 1
    # Used only if bundle discovery does not supply this persisted query.
    _QUERY_HASH_FALLBACKS: ClassVar[dict[str, str]] = {
        # Last independently published web-player hash (2026-11-02).
        # Search operations are now exposed through searchDesktop.
        "searchDesktop": "db61238974d27839a136c9dc02bfdbe3fab7635f21cf85976ebff9a1ee281345",
        # Published in the 2026-11-06 web-player hash registry.
        "getAlbum": "0b6ce3511e1b02e4a40fa95440f992acbe85080eb308af9194322d708fc1914f",
        # Community-reported 2026-04-14 value; no longer listed in the
        # current web bundle. Dynamic discovery always takes precedence.
        "getTrack": "612585ae06ba435ad26369870deaae23b5c8800a256cd8a57e08eddc25a37294",
        "queryArtistOverview": "eafb1620d783ece118e72fbfede2b0064483e029d3c1aafafa1c2de0e25a89e7",
        "queryPodcastEpisodes": "3539d746cf882f3909660de40b4ef472b3f5893a0761d617c282541de5d412c5",
        # Community-reported value; live endpoint validity is not verified.
        "getEpisodeOrChapter": "9697538fe993af785c10725a40bb9265a20b998ccd2383bd6f586e01303824e9",
    }
    _QUERY_URL: ClassVar[str] = "https://api-partner.spotify.com/pathfinder/v2/query"
    _FALLBACK_TOTAL: ClassVar[int] = _DEFAULT_PAGE_CAP

    def __init__(self, session: AuthSession, *, owns_session: bool = False) -> None:
        """Wrap an existing session.

        Args:
            session: Session used to sign every request. It should
                already be authorized; ``create()`` takes care of that.
        """
        self.session = session
        self._owns_session = owns_session
        self._profile: Profile | None = None

    @classmethod
    async def create(cls, *, proxy: str | None = None, language: str = "en") -> Self:
        """Create a client and authorize it.

        If authorization fails, the underlying session is closed before
        the error propagates, so no connection is leaked.

        Returns:
            A ready-to-use, authorized client.

        Raises:
            BaseClientError: Authorization failed.
        """
        language = normalize_language(language)
        session = AuthSession(await AsyncClient.new(proxy=proxy), language=language)
        authorized = False

        try:
            await session.authorize()

            authorized = True
        finally:
            if not authorized:
                await session.close()

        return cls(session, owns_session=True)

    async def close(self) -> None:
        """Close a factory-created session; explicitly supplied sessions stay borrowed."""
        if self._owns_session:
            await self.session.close()

    async def pathfinder_query(
        self,
        variables: dict[str, Any],
        operation_name: str,
        *,
        max_attempts: int | None = None,
    ) -> ObjectDict:
        """Execute a persisted Pathfinder query.

        Args:
            variables: GraphQL variables to send with the operation.
            operation_name: Name of the persisted operation, for example
                ``"searchTracks"``.
            max_attempts: Retry limit for this operation. Use ``1`` for
                mutations that must not be replayed automatically. Unknown
                operations use one attempt unless explicitly overridden;
                known catalogue reads enable transient-failure retries.

        Returns:
            The GraphQL ``data`` object. The HTTP response envelope is
            not included.

        Raises:
            BaseClientError: There is no persisted query hash for
                ``operation_name``, the response body was empty, or it
                contained no ``data`` object.
        """
        query_hash = self.session.session.query_hash(operation_name)

        if not query_hash:
            query_hash = self._QUERY_HASH_FALLBACKS.get(operation_name, "")

        if not query_hash:
            raise BaseClientError(
                f"No persisted query hash for {operation_name!r}; "
                "Spotify may have removed or renamed this operation. "
                "Refresh the web-player query cache or supply a known operation."
            )

        payload: dict[str, Any] = {
            "variables": variables,
            "operationName": operation_name,
            "extensions": {
                "persistedQuery": {
                    "version": self._QUERY_VERSION,
                    "sha256Hash": query_hash,
                }
            },
        }
        headers = {
            **self.session.authorized_headers,
            "accept": "application/json",
            "content-type": "application/json;charset=UTF-8",
        }

        response: Response = await self.session.client.post(
            self._QUERY_URL,
            max_attempts=max_attempts,
            retry_safe=operation_name in _READ_OPERATIONS,
            json=payload,
            headers=headers,
        )

        body = response.json

        if body is None:
            raise BaseClientError("Pathfinder query endpoint returned an empty response body")

        data: object = body.get("data")

        if not isinstance(data, ObjectDict):
            raise BaseClientError(
                f"Pathfinder {operation_name} returned no object data; "
                f"errors={body.get('errors')!r}"
            )

        return data

    async def paginate_query(
        self,
        variables: dict[str, Any],
        operation_name: str,
        *,
        obey_total_count: bool = True,
        return_raw: bool = False,
        extract_page: Callable[[ObjectDict], ObjectDict] | None = None,
    ) -> AsyncGenerator[ObjectDict, None]:
        """Page through a Pathfinder query as an asynchronous generator.

        ``offset`` follows ``pagingInfo.nextOffset`` when supplied, otherwise
        advances by ``limit``.
        Unless ``return_raw`` is set, pages are unwrapped and iteration
        stops when a known ``items`` collection is empty or the reported
        total count has been reached.

        Argument errors surface on the first iteration, not when the
        generator is created.

        Args:
            variables: GraphQL variables. ``limit`` is required;
                ``offset`` is optional and defaults to ``0``.
            operation_name: Name of the persisted operation.
            obey_total_count: Stop at the ``totalCount`` reported by the
                server. If ``False``, or if the server reports none,
                iteration is bounded by a fallback of 1000 results.
            return_raw: Yield whole response envelopes instead of extracted
                pages. Page termination is checked in either mode.
            extract_page: Optional caller-supplied page extractor. Defaults to
                the existing two-level Pathfinder unwrapping heuristic.

        Yields:
            A single page of results.

        Raises:
            KeyError: ``variables`` has no ``limit``.
            ValueError: ``limit`` is not positive.
            BaseClientError: A page request failed. See
                ``pathfinder_query()``.
        """

        async def fetch_page(page_variables: dict[str, Any]) -> ObjectDict:
            """Fetch one page using the current offset and bounded page limit."""
            return await self.pathfinder_query(page_variables, operation_name)

        async for page in paginate(
            fetch_page,
            variables,
            obey_total_count=obey_total_count,
            return_raw=return_raw,
            extract_page=extract_page,
        ):
            yield page

    async def get_profile_attributes(self) -> Profile:
        """Fetch the profile of the authenticated account.

        The result is cached for the lifetime of this client, so only
        the first call performs a request.

        Returns:
            The account's profile attributes.

        Raises:
            BaseClientError: The endpoint returned no profile.
        """
        if self._profile is None:
            response = await self.pathfinder_query({}, "profileAttributes")

            me = response.get("me")

            if not isinstance(me, ObjectDict):
                raise BaseClientError("Profile attributes endpoint returned no profile")

            profile = me.get("profile")

            if not isinstance(profile, ObjectDict):
                raise BaseClientError("Profile attributes endpoint returned no profile")

            self._profile = Profile.from_dict(profile)

        return self._profile


class SharedQueryClient:
    """Own one concurrent query client, draining borrowed requests on close.

    wreq already pools connections. Serializing client creation avoids repeated
    authorization and discovery without serializing the subsequent requests.
    """

    def __init__(self, factory: Callable[[], Awaitable[QueryClient]] | None = None) -> None:
        """Lazily own one loop-local query client created by the optional factory."""
        self._client: QueryClient | None = None
        self._factory = factory
        self._lock = asyncio.Lock()
        self._loop = asyncio.get_running_loop()
        self._borrowers = 0
        self._drained = asyncio.Event()

        self._drained.set()

        self._close_task: asyncio.Task[None] | None = None

    def _check_loop(self) -> None:
        """Reject use from an event loop other than the owner's loop."""
        if asyncio.get_running_loop() is not self._loop:
            raise RuntimeError("Query client belongs to another event loop")

    @asynccontextmanager
    async def acquire(self) -> AsyncGenerator[QueryClient, None]:
        """Borrow the shared query client while counting active in-flight users."""
        self._check_loop()

        if self._close_task is not None:
            raise RuntimeError("Query client is closed")

        self._borrowers += 1
        self._drained.clear()

        try:
            async with self._lock:
                if self._close_task is not None:
                    raise RuntimeError("Query client is closed")

                if self._client is None:
                    self._client = await (
                        self._factory() if self._factory else QueryClient.create()
                    )

                client = self._client

            yield client
        finally:
            self._borrowers -= 1

            if self._borrowers == 0:
                self._drained.set()

    async def close(self) -> None:
        """Reject new requests and finish cleanup even if a waiter is cancelled."""
        self._check_loop()

        if self._close_task is None:
            self._close_task = asyncio.create_task(self._shutdown(), name="spotapi-query-close")

            self._close_task.add_done_callback(_observe_close)

        await asyncio.shield(self._close_task)

    async def _shutdown(self) -> None:
        """Wait for borrowers and close the shared client exactly once."""
        await self._drained.wait()

        client, self._client = self._client, None

        if client is not None:
            await client.close()

    @property
    def closed(self) -> bool:
        """Report whether shutdown has completed."""
        return self._close_task is not None and self._close_task.done()


def _observe_close(task: asyncio.Task[None]) -> None:
    """Observe a retained close task's failure without changing its awaitable result."""
    if not task.cancelled() and (error := task.exception()) is not None:
        _logger.error("Query client shutdown failed", exc_info=error)


@dataclass(slots=True)
class _PoolEntry:
    pool: SharedQueryClient
    reaper: asyncio.Task[None] | None
    closing: bool = False


class _PoolRegistry(threading.local):
    """Pool state is isolated per thread *and* per running event loop."""

    def __init__(self) -> None:
        """Create this thread's registry of event-loop-specific query owners."""
        self.entries: dict[asyncio.AbstractEventLoop, _PoolEntry] = {}


_registry = _PoolRegistry()
_logger = logging.getLogger(__name__)


def _forget(loop: asyncio.AbstractEventLoop, pool: SharedQueryClient) -> None:
    """Remove a closed loop-local client owner from the registry."""
    entry = _registry.entries.get(loop)

    if entry is not None and entry.pool is pool:
        _registry.entries.pop(loop, None)


async def _shutdown(loop: asyncio.AbstractEventLoop, entry: _PoolEntry) -> None:
    """Close and unregister the implicit pool, safely and idempotently."""
    try:
        await entry.pool.close()
    finally:
        if entry.pool.closed:
            _forget(loop, entry.pool)


async def _reap(loop: asyncio.AbstractEventLoop, entry: _PoolEntry) -> None:
    """Best-effort cleanup when ``asyncio.run``/``Runner`` cancels tasks.

    There is no general asynchronous destructor for an arbitrary event
    loop. Applications managing their own loops should use the managed
    wrapper or close the pool during application shutdown.
    """
    try:
        await asyncio.Future()
    finally:
        if not entry.pool.closed:
            try:
                await _shutdown(loop, entry)
            except Exception:
                _logger.exception("Error closing spotapi query clients during loop shutdown")


def query_client_pool() -> SharedQueryClient:
    """Return the lazily-created, per-event-loop shared client owner.

    Normal :class:`Public` calls manage borrowing automatically and do
    not require ``close_query_clients()``. For typical ``asyncio.run``
    applications, pool cleanup is also attempted at loop shutdown.

    Custom, long-lived event loops should integrate deterministic
    cleanup with their application lifecycle instead of relying on
    task cancellation at loop shutdown.
    """
    loop = asyncio.get_running_loop()
    entry = _registry.entries.get(loop)

    if entry is not None:
        if entry.closing and not entry.pool.closed:
            raise RuntimeError("SpotAPI query clients are shutting down")

        if not entry.pool.closed:
            return entry.pool

    if entry is not None:
        _registry.entries.pop(loop, None)

        if entry.pool.closed and entry.reaper is not None:
            entry.reaper.cancel()

    pool = SharedQueryClient()
    # Construct entry and its reaper synchronously on the current event loop.
    # The task cannot run until control returns to the loop.
    entry = _PoolEntry(pool, None)
    entry.reaper = loop.create_task(_reap(loop, entry), name="spotapi-pool-reaper")
    _registry.entries[loop] = entry

    return pool


async def close_query_clients() -> None:
    """Close the implicit pool now, if one exists on this event loop.

    This is intended for framework/application shutdown hooks, not
    normal callers of :class:`Public`.
    """
    loop = asyncio.get_running_loop()
    entry = _registry.entries.get(loop)

    if entry is None:
        return

    entry.closing = True

    try:
        await _shutdown(loop, entry)
    finally:
        if (
            entry.pool.closed
            and entry.reaper is not None
            and entry.reaper is not asyncio.current_task()
        ):
            entry.reaper.cancel()

            # Observe cancellation so the reaper cannot outlive explicit shutdown.
            current = asyncio.current_task()
            cancel_count = current.cancelling() if current is not None else 0

            try:
                await entry.reaper
            except asyncio.CancelledError:
                if current is not None and current.cancelling() > cancel_count:
                    raise
