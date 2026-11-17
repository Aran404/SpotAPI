"""Decode the JSON collection notifications sent by Spotify's dealer."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, cast

from spotapi.types import BaseClientError


def collection_changes(packet: Mapping[str, Any]) -> tuple[tuple[str, bool], ...]:
    """Return saved-state changes for music tracks in a JSON collection event."""
    uri = packet.get("uri", packet.get("ident"))
    if not isinstance(uri, str) or not uri.startswith("hm://collection/collection/"):
        return ()

    if not uri.endswith("/json"):
        return ()

    payloads = packet.get("payloads")
    if not isinstance(payloads, list):
        raise BaseClientError("Collection notification has no payload list")

    changes: list[tuple[str, bool]] = []
    for payload in cast(list[object], payloads):
        if not isinstance(payload, str):
            raise BaseClientError("Collection notification has an invalid JSON payload")

        try:
            decoded: object = json.loads(payload)
        except ValueError as error:
            raise BaseClientError("Collection notification contains invalid JSON") from error

        if not isinstance(decoded, dict):
            raise BaseClientError("Collection notification has no items")

        items = cast(dict[str, object], decoded).get("items")
        if not isinstance(items, list):
            raise BaseClientError("Collection notification has no items")

        for item in cast(list[object], items):
            if not isinstance(item, dict):
                raise BaseClientError("Collection notification contains an invalid item")

            entry = cast(dict[str, object], item)
            if entry.get("type") != "track":
                continue

            identifier, removed = entry.get("identifier"), entry.get("removed")
            if not isinstance(identifier, str) or not identifier or type(removed) is not bool:
                raise BaseClientError("Collection notification has invalid track fields")

            changes.append((f"spotify:track:{identifier}", not removed))

    return tuple(changes)
