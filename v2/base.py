from v2.datastruct import Pool
from v2.types import BaseClientError
from v2.datastruct import ObjectDict

from .session import AuthSession
from .client import AsyncClient

from typing import ClassVar, AsyncGenerator, Any


def get_at_depth(d: ObjectDict, depth: int) -> ObjectDict | None:
    current = d
    for _ in range(depth):
        dict_children = [
            value for value in current.values() if isinstance(value, ObjectDict)
        ]
        if not dict_children:
            return

        current = max(dict_children, key=len)

    return current


async def _base_client_factory() -> BaseClient:
    client = await AsyncClient.new()
    b_client = BaseClient(client)
    await b_client.authorize()
    return b_client


# should've made pool sync
BaseClientPool: Pool[BaseClient] = Pool(
    _base_client_factory,
    teardown=lambda b: b.close(),
)


class BaseClient(AuthSession):
    _QUERY_VERSION: ClassVar[int] = 1
    _QUERY_URL: ClassVar[str] = "https://api-partner.spotify.com/pathfinder/v2/query"

    def __init__(self, client: AsyncClient) -> None:
        super().__init__(client)

    @property
    def authorized_headers(self) -> dict[str, str]:
        if not self.token.client_token:
            raise BaseClientError("Client token not set")

        return {
            "authorization": f"Bearer {self.token.access_token}",
            "client-token": self.token.client_token,
            "spotify-app-version": self.session.server_config.client_version,
            "app-platform": "WebPlayer",
        }

    async def pathfinder_query(
        self, variables: dict[str, Any], operation_name: str
    ) -> ObjectDict:
        payload = {
            "variables": variables,
            "operationName": operation_name,
            "extensions": {
                "persistedQuery": {
                    "version": self._QUERY_VERSION,
                    "sha256Hash": self.session.query_hash(operation_name),
                }
            },
        }
        response = await self.client.post(
            self._QUERY_URL, json=payload, headers=self.authorized_headers
        )

        if not response.json:
            raise BaseClientError(
                "Pathfinder query endpoint returned an empty response body"
            )

        if not isinstance(response.json.data, ObjectDict):
            raise BaseClientError("Query returned a non-object *data* key")

        return response.json.data

    async def paginate_query(
        self,
        variables: dict[str, Any],
        operation_name: str,
        *,
        obey_total_count: bool = True,
    ) -> AsyncGenerator[ObjectDict]:
        total_count: int = 1000
        while variables["offset"] < total_count:
            response = await self.pathfinder_query(variables, operation_name)
            inner_value = get_at_depth(response, 2) or response

            if obey_total_count:
                total_count = inner_value.get("totalCount", 1000)

            if not all(inner_value.values()):
                break

            yield inner_value
            variables["offset"] += variables["limit"]
