from __future__ import annotations

from typing import Any, Unpack, NamedTuple, cast

import wreq

from v2.connection import (
    ClientPool,
    HTTPClient,
    Response,
    ResponseSuccess,
    WebSocketClient,
)
from v2.types import HTTPError


class _RawClients(NamedTuple):
    http: HTTPClient
    ws: WebSocketClient


class AsyncClient:
    __slots__: tuple[str, ...] = (
        "_http",
        "_ws",
        "_proxy",
    )

    def __init__(self, *, proxy: str | None = None) -> None:
        self._proxy = proxy
        self._http: HTTPClient
        self._ws: WebSocketClient

    @property
    def protocols(self) -> _RawClients:
        return _RawClients(self._http, self._ws)

    @classmethod
    async def new(cls, *, proxy: str | None = None, **kwargs: Any) -> AsyncClient:
        self = cls(proxy=proxy)
        await self._setup(**kwargs)
        return self

    async def __aenter__(self) -> AsyncClient:
        await self._setup()
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def close(self) -> None:
        if self._proxy:
            await self._http.close()
        else:
            ClientPool.put(self._http)

    async def _setup(self, **kwargs: Any) -> None:
        if self._proxy:
            self._http = HTTPClient(
                proxies=[
                    wreq.Proxy.http(self._proxy),
                    wreq.Proxy.https(self._proxy),
                ],
                **kwargs,
            )
        else:
            self._http = await ClientPool.get()

        self._ws = WebSocketClient(http_client=self._http)

    async def get(self, url: str, **kwargs: Unpack[wreq.Request]) -> ResponseSuccess:
        return _validate(await self._http.get(url, **kwargs))

    async def post(self, url: str, **kwargs: Unpack[wreq.Request]) -> ResponseSuccess:
        return _validate(await self._http.post(url, **kwargs))

    async def put(self, url: str, **kwargs: Unpack[wreq.Request]) -> ResponseSuccess:
        return _validate(await self._http.put(url, **kwargs))

    async def delete(self, url: str, **kwargs: Unpack[wreq.Request]) -> ResponseSuccess:
        return _validate(await self._http.delete(url, **kwargs))

    async def head(self, url: str, **kwargs: Unpack[wreq.Request]) -> ResponseSuccess:
        return _validate(await self._http.head(url, **kwargs))

    async def patch(self, url: str, **kwargs: Unpack[wreq.Request]) -> ResponseSuccess:
        return _validate(await self._http.patch(url, **kwargs))


def _validate(response: Response) -> ResponseSuccess:
    if response.status_code is None or response.text is None:
        raise HTTPError("Invalid response object returned")

    if not response.status_code.is_success():
        raise HTTPError(
            f"Request returned non-ok status code: {response.status_code.as_int()}"
        )

    content_type = response.headers.get("content-type") if response.headers else None
    if (
        content_type
        and "application/json" in str(content_type)
        and response.json is None
    ):
        raise HTTPError(
            "Expected a JSON payload (application/json), but received an empty body."
        )

    return cast(ResponseSuccess, response)
