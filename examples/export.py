"""Export typed playlist metadata with Python's standard JSON tools."""

import asyncio
import json
from dataclasses import asdict

from spotapi import Public


async def main() -> None:
    playlist = await Public.get_playlist("37i9dQZF1DXcBWIGoYBM5M")

    print(json.dumps(asdict(playlist), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
