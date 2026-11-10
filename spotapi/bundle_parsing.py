"""Parse Spotify's deployed webpack filenames and persisted-query hashes."""

from __future__ import annotations

import ast
import re
from itertools import islice

__all__ = ("extract_mappings", "combine_chunks", "extract_js_links", "extract_query_hashes")

_CHUNK_MAP_RE = re.compile(r'\{\d+:"[^"]+"(?:,\d+:"[^"]+")*\}')
_QUERY_HASH_RE = re.compile(r'"([^"]+)",\s*"(?:query|mutation)",\s*"([^"]+)"')
_JS_URL_RE = re.compile(r"""["'](https?://[^"']+\.js(?:\?[^"']*)?)["']""", re.I)


def extract_mappings(js_code: str) -> tuple[dict[int, str], dict[int, str]]:
    """Extract webpack chunk hashes and names from a Spotify bundle.

    Returns:
        A ``(hashes, names)`` pair, keyed by chunk ID.

    Raises:
        ValueError: If no usable pair of chunk maps can be found.
    """
    # JS and CSS loaders often have identical chunk IDs but different hashes.
    # Read the two maps belonging to webpack's JS filename function together.
    loader = re.search(r"\.u\s*=\s*(?:[\w$]+\s*=>|function\s*\()", js_code)
    matches = _CHUNK_MAP_RE.finditer(js_code, loader.end() if loader else 0)
    selected = islice(matches, 2) if loader else matches
    maps: list[dict[int, str]] = [ast.literal_eval(match.group()) for match in selected]

    if len(maps) < 2:
        raise ValueError("Could not find both webpack chunk maps")

    # Prefer the hash-like mapping, rather than assuming it is the fourth
    # object in the minified JavaScript (which changes between builds).
    def score(mapping: dict[int, str]) -> int:
        """Count hash-like values to distinguish webpack hashes from chunk names."""
        return sum(bool(re.fullmatch(r"[0-9a-f]{8,}", value)) for value in mapping.values())

    hash_map = max(maps, key=score)

    if score(hash_map):
        others = [mapping for mapping in maps if mapping is not hash_map]
        name_map = max(others, key=lambda mapping: len(mapping.keys() & hash_map.keys()))

        if hash_map.keys() & name_map.keys():
            return hash_map, name_map

    # Some builds use short or non-hex chunk hashes. Keep the original
    # bundle ordering as a compatibility fallback, without indexing blindly.
    start = 3 if len(maps) >= 5 else len(maps) - 2

    return maps[start], maps[start + 1]


def combine_chunks(name_map: dict[int, str], hash_map: dict[int, str]) -> list[str]:
    """Build chunk filenames where both a name and a hash are known."""
    return [f"{name}.{hash_map[key]}.js" for key, name in name_map.items() if key in hash_map]


def extract_js_links(html_content: str) -> list[str]:
    """Extract distinct Spotify JavaScript URLs from HTML."""
    return sorted({url for url in _JS_URL_RE.findall(html_content) if "spotify" in url})


def extract_query_hashes(content: str) -> dict[str, str]:
    """Extract persisted GraphQL operation hashes from a JavaScript bundle."""
    return dict(_QUERY_HASH_RE.findall(content))
