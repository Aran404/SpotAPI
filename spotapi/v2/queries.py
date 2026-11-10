"""Persisted catalogue queries, pagination and decoding.

Queries manages requests and optional caller-chosen deserialization.
Spotify-specific variables and response parsing belong in ``Catalogue``.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import MISSING, asdict, fields, is_dataclass
from typing import Any, Final, TypeVar, cast, overload

import wreq

from .connection import Response
from .connection.types import Methods
from .datastruct import ObjectDict, Pool
from .operations import InclusionParameters, Operations
from .query import QueryClient, SharedQueryClient, paginate, query_client_pool
from .specialized.data_wrappers import from_dict
from .types import BaseClientError

__all__ = ("Queries",)

_ResultT = TypeVar("_ResultT")
_LOG = logging.getLogger(__name__)
_DEFAULT_PARAMETERS: Final = asdict(InclusionParameters())


def _camel_case(name: str) -> str:
    """Convert ``snake_case`` to ``camelCase``."""
    head, *rest = name.split("_")

    return head + "".join(part.title() for part in rest)


def _required_fields(typ: type | None) -> dict[str, str]:
    """Map each required dataclass field to its camelCase API alias."""
    if typ is None or not is_dataclass(typ):
        return {}

    return {
        item.name: _camel_case(item.name)
        for item in fields(typ)
        if item.init and item.default is MISSING and item.default_factory is MISSING
    }


def _has_field(data: Mapping[str, Any], name: str, alias: str) -> bool:
    """Check the key spellings accepted by the response decoder."""
    return name in data or alias in data


class Queries:
    """Execute persisted queries and decode their results."""

    __slots__ = ("_pool",)

    def __init__(self, pool: Pool[QueryClient] | SharedQueryClient | None = None) -> None:
        """Use ``pool`` if supplied, otherwise lazily use the shared client."""
        self._pool = pool

    def __repr__(self) -> str:
        """Return a concise diagnostic representation."""
        pool = "custom" if self._pool is not None else "shared"

        return f"<Queries pool={pool}>"

    def _get_pool(self) -> Pool[QueryClient] | SharedQueryClient:
        """Use the injected query owner or lazily acquire the shared owner."""
        return self._pool if self._pool is not None else query_client_pool()

    @classmethod
    @asynccontextmanager
    async def open(cls) -> AsyncGenerator[Queries, None]:
        """Own a private client scope for deterministic application-level cleanup."""
        pool = SharedQueryClient()

        try:
            yield cls(pool)
        finally:
            await pool.close()

    @staticmethod
    def extract_data(item: ObjectDict) -> ObjectDict:
        """Unwrap a search hit down to its ``data`` payload."""
        if isinstance(data := item.get("data"), ObjectDict):
            return data

        for value in item.values():
            if isinstance(value, ObjectDict) and isinstance(data := value.get("data"), ObjectDict):
                return data

        return item

    @staticmethod
    def resource_data(
        response: ObjectDict,
        operation: Operations,
        typ: type[_ResultT] | None = None,
        expected_uri: str | None = None,
    ) -> ObjectDict:
        """Extract a single resource from a GraphQL response."""
        payload = cast(Mapping[str, Any], response)
        nested = payload.get("data")

        if "uri" not in payload and isinstance(nested, Mapping):
            payload = cast(Mapping[str, Any], nested)

        required = _required_fields(typ)

        def missing(obj: Mapping[str, Any]) -> list[str]:
            """List required model fields absent under both accepted key spellings."""
            return [name for name, alias in required.items() if not _has_field(obj, name, alias)]

        candidates: list[tuple[str, Mapping[str, Any]]]

        if "uri" in payload:
            candidates = [("resource", payload)]
        else:
            candidates = [
                (key, cast(Mapping[str, Any], value))
                for key, value in payload.items()
                if isinstance(value, Mapping)
            ]

        # 1) The object carrying the URI that was asked for.
        matches = [
            (key, obj)
            for key, obj in candidates
            if expected_uri is not None and obj.get("uri") == expected_uri
        ]

        # 2) Otherwise, the object that has the fields the model needs.
        if not matches:
            matches = [
                (key, obj)
                for key, obj in candidates
                if (expected_uri is None or "uri" not in obj) and not missing(obj)
            ]

        if len(matches) != 1:
            reason = "ambiguous" if matches else "missing"
            raise BaseClientError(f"{operation.value}: {reason} resource in GraphQL response")

        root, resource = matches[0]

        if absent := missing(resource):
            raise BaseClientError(
                f"{operation.value}: {root} missing required fields: {', '.join(absent)}"
            )

        return cast(ObjectDict, resource)

    async def query(
        self,
        operation: str,
        variables: Mapping[str, Any],
    ) -> ObjectDict:
        """Execute a persisted GraphQL operation without interpreting its data."""
        async with self._get_pool().acquire() as client:
            return await client.pathfinder_query(dict(variables), operation)

    async def get_json(self, url: str, *, query: dict[str, str] | None = None) -> ObjectDict:
        """Read a JSON object using the catalogue session."""
        async with self._get_pool().acquire() as client:
            response = await client.session.client.get(
                url, query=query or {}, headers=client.session.authorized_headers
            )

        if response.json is None:
            raise BaseClientError("Catalogue endpoint returned no JSON object")

        return response.json

    async def request(
        self,
        method: Methods,
        url: str,
        *,
        query: Mapping[str, str] | None = None,
        json: Mapping[str, Any] | None = None,
        body: bytes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Response:
        """Use the same authorized transport for an endpoint outside Pathfinder."""
        async with self._get_pool().acquire() as client:
            options: wreq.Request = {
                "headers": {**client.session.authorized_headers, **(headers or {})}
            }
            if query is not None:
                options["query"] = dict(query)
            if json is not None:
                options["json"] = json
            if body is not None:
                options["body"] = body
            return await client.session.client.request(method, url, max_attempts=1, **options)

    async def paginate(
        self,
        operation: str,
        variables: Mapping[str, Any],
        *,
        obey_total_count: bool = True,
        return_raw: bool = False,
        extract_page: Callable[[ObjectDict], ObjectDict] | None = None,
    ) -> AsyncGenerator[ObjectDict, None]:
        """Stream raw pages from any offset/limit operation."""

        async def fetch(page_variables: dict[str, Any]) -> ObjectDict:
            """Fetch and parse the next page without retaining earlier pages."""
            return await self.query(operation, page_variables)

        async for page in paginate(
            fetch,
            dict(variables),
            obey_total_count=obey_total_count,
            return_raw=return_raw,
            extract_page=extract_page,
        ):
            yield page

    async def search(
        self,
        query: str,
        /,
        operation: Operations,
        *,
        obey_total_count: bool = True,
        parameters: InclusionParameters | None = None,
        extract_page: Callable[[ObjectDict], ObjectDict] | None = None,
    ) -> AsyncGenerator[ObjectDict, None]:
        """Yield raw search pages."""
        variables: dict[str, Any] = {
            "searchTerm": query,
            "offset": 0,
            **(_DEFAULT_PARAMETERS if parameters is None else asdict(parameters)),
            "isPrefix": None,
            "sectionFilters": ["GENERIC"],
        }

        async for page in self.paginate(
            operation.value,
            variables,
            obey_total_count=obey_total_count,
            extract_page=extract_page,
        ):
            yield page

    @staticmethod
    def parse_items(
        page: ObjectDict,
        typ: type[_ResultT],
        operation: Operations,
        *,
        skip_invalid: bool = False,
    ) -> list[_ResultT]:
        """Deserialize a search section into instances of ``typ``."""
        # Read the original Spotify key first. ``_items`` is only the
        # attribute-access spelling used by ObjectDict for the key ``items``.
        # Keep the leading-underscore fallback for callers holding older
        # pre-normalized page objects.
        items: object = page["items"] if "items" in page else page.get("_items")

        if not isinstance(items, list):
            raise BaseClientError(f"{operation.value}: missing search items")

        required = _required_fields(typ)
        results: list[_ResultT] = []

        for item in cast(list[object], items):
            if not isinstance(item, ObjectDict):
                if skip_invalid:
                    continue

                raise BaseClientError(f"{operation.value}: invalid search item")

            # Spotify includes placeholder entries for removed resources.
            if item.get("data", object()) is None or any(
                isinstance(value, ObjectDict) and value.get("data", object()) is None
                for value in item.values()
            ):
                continue

            payload = Queries.extract_data(item)

            if any(not _has_field(payload, name, alias) for name, alias in required.items()):
                # Search may return lightweight previews that cannot satisfy
                # the requested model. They are not malformed page envelopes.
                continue

            try:
                parsed = from_dict(typ, payload)
            except (LookupError, TypeError, ValueError, AttributeError):
                if not skip_invalid:
                    raise

                _LOG.debug(
                    "Skipping malformed %s search result",
                    typ.__name__,
                    exc_info=True,
                )

                continue

            results.append(parsed)

        return results

    @staticmethod
    def parse_raw_items(
        page: ObjectDict,
        operation: Operations,
        *,
        skip_invalid: bool = False,
    ) -> list[ObjectDict]:
        """Extract raw entity payloads from a search section."""
        items: object = page["items"] if "items" in page else page.get("_items")

        if not isinstance(items, list):
            raise BaseClientError(f"{operation.value}: missing search items")

        results: list[ObjectDict] = []

        for item in cast(list[object], items):
            if not isinstance(item, ObjectDict):
                if skip_invalid:
                    continue

                raise BaseClientError(f"{operation.value}: invalid search item")

            if item.get("data", object()) is None or any(
                isinstance(value, ObjectDict) and value.get("data", object()) is None
                for value in item.values()
            ):
                continue

            results.append(Queries.extract_data(item))

        return results

    async def typed_search(
        self,
        typ: type[_ResultT],
        operation: Operations,
        query: str,
        /,
        *,
        parameters: InclusionParameters | None = None,
        extract_page: Callable[[ObjectDict], ObjectDict] | None = None,
        skip_invalid: bool = False,
    ) -> AsyncGenerator[Sequence[_ResultT], None]:
        """Yield search pages parsed into instances of ``typ``."""
        async for page in self.search(
            query,
            operation=operation,
            parameters=parameters,
            extract_page=extract_page,
        ):
            yield self.parse_items(page, typ, operation, skip_invalid=skip_invalid)

    async def direct_query(
        self,
        uri: str,
        /,
        operation: Operations,
    ) -> ObjectDict:
        """Fetch one resource without pagination."""
        variables: dict[str, Any] = {
            "uri": uri,
            "locale": "",
            "offset": 0,
            "limit": 100,
            "enableWatchFeedEntrypoint": False,
            "includeEpisodeContentRatingsV2": True,
        }

        return await self.query(operation.value, variables)

    @overload
    async def resource(self, uri: str, operation: Operations, /) -> ObjectDict: ...

    @overload
    async def resource(
        self, uri: str, operation: Operations, typ: type[_ResultT], /
    ) -> _ResultT: ...

    async def resource(
        self,
        uri: str,
        operation: Operations,
        typ: type[_ResultT] | None = None,
        /,
    ) -> ObjectDict | _ResultT:
        """Fetch one resource, optionally parsed into a dataclass."""
        response = await self.direct_query(uri, operation=operation)

        if typ is None:
            return response

        resource = self.resource_data(response, operation, typ, uri)

        try:
            result = from_dict(typ, resource)
        except (LookupError, TypeError, ValueError, AttributeError) as exc:
            raise BaseClientError(
                f"{operation.value}: failed to deserialize {typ.__name__}: {exc}"
            ) from exc

        if not isinstance(result, typ):
            raise BaseClientError(
                f"{operation.value}: expected {typ.__name__}, got {type(result).__name__}"
            )

        return result
