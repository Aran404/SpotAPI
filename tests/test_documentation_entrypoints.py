"""Check local paths in the public developer-entry documentation."""

from __future__ import annotations

import re
import tomllib
from hashlib import sha1
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
        "README.fr.md",
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


# English README Git blob SHA at translation time. Changes to the canonical
# README must be reviewed against *all* translations, even when only prose changes.
_ENGLISH_README_BLOB_SHA = "b91592b23ad6a940e3279f63efcbd0743fd62157"
_TRANSLATIONS = ("README.pt-BR.md", "README.es.md", "README.fr.md")
_LANGUAGES = ("README.md", *_TRANSLATIONS)


def _git_blob_sha(content: bytes) -> str:
    header = b"blob " + str(len(content)).encode("ascii") + b"\0"
    return sha1(header + content).hexdigest()


def _fenced_code(text: str) -> list[str]:
    return re.findall(r"^```[^\n]*\n[\s\S]*?^```[ \t]*$", text, re.MULTILINE)


def _inline_code(text: str) -> list[str]:
    stripped = re.sub(r"^```[^\n]*\n[\s\S]*?^```[ \t]*$", "", text, flags=re.MULTILINE)
    return re.findall(r"(?<!`)`([^`\n]+)`(?!`)", stripped)


def _headings(text: str) -> list[int]:
    return [len(marker) for marker in re.findall(r"^(#{2,3}) ", text, re.MULTILINE)]


def _media_paths(text: str) -> list[str]:
    markdown = re.findall(r"!\[[^\]]*\]\(([^)]+)\)", text)
    html = re.findall(r'<img\s+src="([^"]+)"', text)
    return [*markdown, *html]


def _destination_paths(text: str) -> list[str]:
    markdown = re.findall(r"\]\(([^)\s]+)\)", text)
    html = re.findall(r'href="([^"]+)"', text)
    return sorted(
        target
        for target in (*markdown, *html)
        if not target.startswith("#") and target not in _LANGUAGES
    )


def _heading_slug(title: str) -> str:
    # Covers the plain GitHub-style headings used by our README translations.
    return re.sub(r"\s+", "-", re.sub(r"[^\w\s-]", "", title.lower()).strip())


@pytest.mark.parametrize("filename", _TRANSLATIONS)
def test_localized_readme_has_full_english_structure(filename: str) -> None:
    english_bytes = (ROOT / "README.md").read_bytes()
    english = english_bytes.decode("utf-8")
    translated = (ROOT / filename).read_text(encoding="utf-8")

    assert _git_blob_sha(english_bytes) == _ENGLISH_README_BLOB_SHA, (
        "README.md changed: review/update Portuguese, Spanish, and French "
        "translations, then update the reviewed English blob SHA."
    )

    assert len(translated.splitlines()) == len(english.splitlines())
    assert _fenced_code(translated) == _fenced_code(english)
    assert _inline_code(translated) == _inline_code(english)
    assert _headings(translated) == _headings(english)
    assert _media_paths(translated) == _media_paths(english)
    assert _destination_paths(translated) == _destination_paths(english)

    assert sum(line.startswith("|") for line in translated.splitlines()) == sum(
        line.startswith("|") for line in english.splitlines()
    )
    assert sum(line.startswith("- ") for line in translated.splitlines()) == sum(
        line.startswith("- ") for line in english.splitlines()
    )

    headings = {
        _heading_slug(title) for title in re.findall(r"^#{2,3} (.+)$", translated, re.MULTILINE)
    }
    anchors = [
        *re.findall(r'href="#([^"]+)"', translated),
        *re.findall(r"\]\(#([^)]+)\)", translated),
    ]
    for anchor in anchors:
        assert anchor in headings, f"{filename}: unresolved section anchor #{anchor}"

    for language in _LANGUAGES:
        if language != filename:
            assert (
                f'href="{language}"' in translated
            ), f"{filename}: missing language-switch link for {language}"
