from __future__ import annotations

from spotapi.v2.datastruct import Pool
from spotapi.v2.types import BaseClientError
from spotapi.v2.datastruct import ObjectDict
from spotapi.v2.specialized.data_wrappers import Profile

from spotapi.v2.session import AuthSession
from spotapi.v2.client import AsyncClient

from typing import ClassVar, AsyncGenerator, Any


def get_at_depth(d: ObjectDict, depth: int) -> ObjectDict | None:
    current = d
    for _ in range(depth):
        dict_children = [value for value in current.values() if isinstance(value, ObjectDict)]
        if not dict_children:
            return

        current = max(dict_children, key=len)

    return current


async def _query_client_factory() -> QueryClient:
    client = await AsyncClient.new()
    session = AuthSession(client)
    await session.authorize()

    return QueryClient(session)


# should've made pool sync
QueryClientPool: Pool[QueryClient] = Pool(
    _query_client_factory,
    teardown=lambda b: b.session.close(),
)


class QueryClient:
    __slots__: tuple[str, ...] = (
        "session",
        "_profile",
    )
    _QUERY_VERSION: ClassVar[int] = 1
    _QUERY_URL: ClassVar[str] = "https://api-partner.spotify.com/pathfinder/v2/query"

    def __init__(self, session: AuthSession) -> None:
        self.session = session
        self._profile: Profile | None = None

    async def pathfinder_query(self, variables: dict[str, Any], operation_name: str) -> ObjectDict:
        payload = {
            "variables": variables,
            "operationName": operation_name,
            "extensions": {
                "persistedQuery": {
                    "version": self._QUERY_VERSION,
                    "sha256Hash": self.session.session.query_hash(operation_name),
                }
            },
        }
        print(payload)
        headers = {
            **self.session.authorized_headers,
            "accept": "application/json",
            "content-type": "application/json;charset=UTF-8",
        }
        response = await self.session.client.post(
            self._QUERY_URL,
            json=payload,
            headers=headers,
        )
        if not response.json:
            raise BaseClientError("Pathfinder query endpoint returned an empty response body")

        if not isinstance(response.json.data, ObjectDict):
            raise BaseClientError("Query returned a non-object *data* key")

        return response.json.data

    async def paginate_query(
        self,
        variables: dict[str, Any],
        operation_name: str,
        *,
        obey_total_count: bool = True,
        return_raw: bool = False,
    ) -> AsyncGenerator[ObjectDict]:
        total_count: int = 1000
        while variables["offset"] < total_count:
            response = await self.pathfinder_query(variables, operation_name)
            if not return_raw:
                response = get_at_depth(response, 2) or response

                if obey_total_count:
                    total_count = response.get("totalCount", 1000)

                if not all(response.values()):
                    break

            yield response
            variables["offset"] += variables["limit"]

    async def get_profile_attributes(self) -> Profile:
        """Fetches and caches profile attributes asynchronously."""
        if self._profile is not None:
            return self._profile

        response = await self.pathfinder_query({}, "profileAttributes")

        if not (response and response.me and response.me.profile):
            raise BaseClientError("Profile attributes endpoint returned an empty response body")

        self._profile = Profile.from_dict(response.me.profile)
        return self._profile
