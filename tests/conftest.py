"""One switch controls all integration tests; ordinary runs stay offline."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv


def pytest_addoption(parser: pytest.Parser) -> None:
    """Register read-only and explicitly mutating live-test modes."""
    parser.addoption(
        "--live",
        choices=("off", "read", "all"),
        default="off",
        help="Spotify checks: --live=read for reads, --live=all includes playback and temporary-playlist changes",
    )


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Apply integration policy centrally, loading local credentials only on opt-in."""
    mode = config.getoption("live")
    if mode != "off":
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    for item in items:
        if item.get_closest_marker("live") is None:
            continue
        reason = None
        if mode == "off":
            reason = "use --live=read for Spotify integration checks"
        elif item.get_closest_marker("mutates") is not None and mode != "all":
            reason = "use --live=all to allow playback changes"
        elif item.get_closest_marker("authenticated") is not None and not os.getenv(
            "SPOTIFY_COOKIE"
        ):
            reason = "authenticated checks require SPOTIFY_COOKIE"
        if reason:
            item.add_marker(pytest.mark.skip(reason=reason))
