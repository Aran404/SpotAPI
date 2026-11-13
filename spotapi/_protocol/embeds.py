"""Extract public embed metadata without retaining session-bearing HTML."""

from __future__ import annotations

import json
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any

from spotapi._parsing import mapping
from spotapi.types import BaseClientError


class EmbedMetadataParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.active = False
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.active = dict(attrs).get("id") == "__NEXT_DATA__"

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self.active = False

    def handle_data(self, data: str) -> None:
        if self.active:
            self.parts.append(data)


def entity_from_html(source: str, expected_uri: str) -> Mapping[str, Any]:
    if len(source) > 8 * 1024 * 1024:
        raise BaseClientError("Spotify embed page exceeds 8 MiB")
    parser = EmbedMetadataParser()
    parser.feed(source)
    try:
        body = mapping(json.loads("".join(parser.parts)))
    except ValueError as error:
        raise BaseClientError("Spotify embed page has no valid metadata") from error
    props = mapping(mapping(body.get("props")).get("pageProps"))
    entity = mapping(mapping(mapping(props.get("state")).get("data")).get("entity"))
    if entity.get("uri") != expected_uri:
        raise BaseClientError("Spotify embed page returned a different or missing resource")
    return entity
