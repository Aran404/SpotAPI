"""Command-line access to the public catalogue."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict

from .public import Public
from .types import SpotAPIError


def main(argv: Sequence[str] | None = None) -> int:
    """Run a public lookup or track search and return a process exit code."""
    parser = argparse.ArgumentParser(prog="spotapi", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    search = commands.add_parser("search", help="search for tracks")
    search.add_argument("query", help="track or artist to search for")
    get = commands.add_parser("get", help="look up a Spotify URL or URI as JSON")
    get.add_argument("resource", help="Spotify URL or URI")
    args = parser.parse_args(argv)

    try:
        if args.command == "search":
            query: str = args.query
            results = asyncio.run(Public.search(query, types="track", limit=10))
            for track in results.tracks:
                print(f"{track.name}\t{track.uri}")
            if not results.tracks:
                print("No tracks found.", file=sys.stderr)
        else:
            resource: str = args.resource
            item = asyncio.run(Public.get(resource))
            payload = item if isinstance(item, dict) else asdict(item)
            print(json.dumps(payload, indent=2, default=str))
    except (SpotAPIError, ValueError) as error:
        print(f"spotapi: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130

    return 0
