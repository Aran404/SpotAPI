"""Find transitions in a public playlist using tempo and Camelot keys."""

import argparse
import asyncio
import re
from contextlib import aclosing
from itertools import combinations

from spotapi import Catalogue

DEFAULT_PLAYLIST = "37i9dQZF1DXcBWIGoYBM5M"


def compatible(left: str, right: str) -> bool:
    """Allow the same key, a neighboring number, or the relative major/minor."""
    a = re.fullmatch(r"(1[0-2]|[1-9])([AB])", left)
    b = re.fullmatch(r"(1[0-2]|[1-9])([AB])", right)
    if a is None or b is None:
        return False

    distance = abs(int(a[1]) - int(b[1]))
    return distance == 0 or (a[2] == b[2] and distance in (1, 11))


async def main(uri: str) -> None:
    async with (
        Catalogue() as spotify,
        aclosing(spotify.get_playlist_tracks(uri, limit=40)) as pages,
    ):
        tracks = await anext(pages, ())

    metadata = {
        track.uri: (track.name, bpm, key)
        for track in tracks
        if (bpm := track.bpm) is not None and bpm > 0 and (key := track.camelot_key)
    }
    transitions: list[tuple[float, str, str, float]] = []
    for left, right in combinations(metadata, 2):
        _, left_bpm, left_key = metadata[left]
        _, right_bpm, right_key = metadata[right]
        shift = 100 * (left_bpm / right_bpm - 1)
        if abs(shift) <= 6 and compatible(left_key, right_key):
            transitions.append((abs(shift), left, right, shift))

    print(f"{len(metadata)} tracks with tempo and key; {len(transitions)} possible transitions")
    for _, left, right, shift in sorted(transitions)[:8]:
        a, a_bpm, a_key = metadata[left]
        b, b_bpm, b_key = metadata[right]
        adjustment = round(shift, 1) or 0.0
        print(f"{a} ({a_bpm:g} BPM, {a_key}) -> {b} ({b_bpm:g} BPM, {b_key})")
        print(
            f"  Match incoming tempo: {adjustment:+.1f}%  https://open.spotify.com/track/{right.rsplit(':', 1)[-1]}"
        )

    if not transitions:
        print("Try a playlist with more tracks in a similar tempo range.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "playlist", nargs="?", default=DEFAULT_PLAYLIST, help="Public Spotify playlist"
    )
    args = parser.parse_args()
    playlist: str = args.playlist
    asyncio.run(main(playlist))
