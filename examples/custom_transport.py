"""Use an explicitly owned transport; optionally set SPOTAPI_PROXY."""

import asyncio
import os

from spotapi import AsyncClient


async def main() -> None:
    async with AsyncClient(proxy=os.environ.get("SPOTAPI_PROXY")) as client:
        response = await client.get("https://open.spotify.com/")

        print(response.status_code.as_int())


if __name__ == "__main__":
    asyncio.run(main())
