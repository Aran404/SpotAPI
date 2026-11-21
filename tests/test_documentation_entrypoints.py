"""Check local paths in the public developer-entry documentation."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
MARKDOWN_LINK = re.compile(r"\]\(([^)\s]+)(?:\s+\"[^\"]+\")?\)")
HTML_LINK = re.compile(r"""href=["']([^"']+)["']""")


@pytest.mark.parametrize(
    "filename",
    [
        "README.md",
        "README.pt-BR.md",
        "README.es.md",
        "examples/README.md",
        "docs/quickstart.md",
        "docs/release-checks.md",
    ],
)
def test_local_markdown_links_point_to_real_files(filename: str) -> None:
    source = ROOT / filename
    contents = source.read_text(encoding="utf-8")
    destinations = [
        *(match.group(1) for match in MARKDOWN_LINK.finditer(contents)),
        *(match.group(1) for match in HTML_LINK.finditer(contents)),
    ]
    for destination in destinations:
        parsed = urlsplit(destination)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue
        target = (source.parent / unquote(parsed.path)).resolve()
        assert target.is_relative_to(ROOT), f"{filename}: path escapes repository"
        assert target.exists(), f"{filename}: broken relative link to {destination}"


def test_readme_connect_extra_is_declared() -> None:
    package = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    extras = package["project"]["optional-dependencies"]
    assert any(item.startswith("textual") for item in extras["connect"])
    assert any(item.startswith("keyring") for item in extras["connect"])


def test_quickstart_points_to_current_anchor() -> None:
    quickstart = (ROOT / "docs/quickstart.md").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "#first-search" not in quickstart
    assert "## Get started" in readme
    assert "SpotAPI Studio desktop application preview" in readme
