"""A focused presentation of one catalogue resource."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from html import unescape
from typing import Any, cast

from rich.columns import Columns
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


@dataclass(frozen=True, slots=True)
class Artwork:
    url: str
    label: str


@dataclass(frozen=True, slots=True)
class Detail:
    title: str
    kind: str
    content: Group
    artwork: tuple[Artwork, ...]


def node(value: object) -> Mapping[str, Any]:
    return cast(Mapping[str, Any], value) if isinstance(value, Mapping) else {}


def items(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, (list, tuple)):
        return []

    return [node(item) for item in cast(list[object], value)]


def at(value: Mapping[str, Any], *path: str) -> Mapping[str, Any]:
    for key in path:
        value = node(value.get(key))

    return value


def clean(value: object) -> str:
    return unescape(re.sub(r"<[^>]+>", "", str(value or ""))).strip()


def artwork(value: Mapping[str, Any], label: str) -> Artwork | None:
    sources = items(value.get("sources"))
    sources = [source for source in sources if source.get("url")]

    if not sources:
        return None

    source = min(sources, key=lambda source: abs((source.get("width") or 300) - 300))

    return Artwork(str(source["url"]), label)


def present(name: str, uri: str, payload: object) -> Detail:
    data = node(payload)
    kind = uri.split(":")[1].title()

    if kind == "Show":
        kind = "Audiobook" if "authors_v2" in data else "Podcast"

    value = node(data.get("track") or data.get("artist") or data.get("playlist") or data)
    album = at(value, "album_of_track")
    artists = items(at(value, "first_artist").get("items")) or items(
        at(value, "artists").get("items")
    )
    artist: Mapping[str, Any] = artists[0] if artists else {}
    artist_name = at(artist, "profile").get("name") or artist.get("name")
    images = [
        artwork(at(album or value, "cover_art"), "Cover artwork"),
        artwork(at(value, "visuals", "avatar_image"), "Artist portrait"),
        artwork(at(artist, "visuals", "avatar_image"), clean(artist_name) or "Artist portrait"),
    ]

    if not any(images):
        image_groups = items(at(value, "images").get("items"))

        images.append(artwork(image_groups[0], "Cover artwork") if image_groups else None)

    if not any(images):
        images.extend(
            (
                artwork(at(value, "image"), "Cover artwork"),
                artwork(at(value, "avatar"), "Profile portrait"),
            )
        )

    if image_url := value.get("image_url"):
        images.append(Artwork(str(image_url), "Profile portrait"))

    if releases := items(data.get("releases")):
        images.append(
            artwork(
                at(releases[0], "cover_art"), "Latest release · " + clean(releases[0].get("name"))
            )
        )

    images.append(artwork(at(value, "owner_v2", "data", "avatar"), "Curator portrait"))

    content = reading(value, album, artist_name, data)
    selected = {image.url: image for image in images if image is not None}

    return Detail(name, kind, content, tuple(selected.values())[:2])


def reading(
    value: Mapping[str, Any],
    album: Mapping[str, Any],
    artist_name: object,
    data: Mapping[str, Any],
) -> Group:
    facts = Table.grid(padding=(0, 3))

    facts.add_column(style="dim")
    facts.add_column(style="bold white")

    fields: list[tuple[str, object]] = [
        ("Artist", artist_name),
        ("Album", album.get("name")),
        ("Released", at(album or value, "date").get("iso_string")),
        ("Plays", value.get("playcount")),
        (
            "Followers",
            at(value, "stats").get("followers")
            or value.get("followers")
            or value.get("followers_count"),
        ),
        ("Monthly listeners", at(value, "stats").get("monthly_listeners")),
        ("World ranking", at(value, "stats").get("world_rank")),
        (
            "Tracks",
            at(value, "content").get("total_count") or at(value, "tracks").get("total_count"),
        ),
        ("Label", value.get("label") or at(data, "album").get("label")),
        (
            "Authors",
            ", ".join(clean(author.get("name")) for author in items(value.get("authors_v2"))),
        ),
        (
            "Rating",
            (
                "Explicit"
                if at(value, "content_rating").get("label") == "EXPLICIT"
                else "Clean" if at(value, "content_rating").get("label") == "NONE" else None
            ),
        ),
        ("Publisher", at(value, "publisher").get("name")),
        ("Owner", at(value, "owner_v2", "data").get("name")),
    ]
    duration = (at(value, "duration") or at(value, "audiobook_duration")).get("total_milliseconds")

    if isinstance(duration, int):
        seconds = duration // 1000

        fields.insert(2, ("Duration", f"{seconds // 60}:{seconds % 60:02}"))

    for label, raw in fields:
        if raw is not None and raw != "":
            if label in {"Plays", "Followers", "Monthly listeners"} and str(raw).isdigit():
                raw = int(str(raw))

            text = f"{raw:,}" if isinstance(raw, int) else clean(raw)

            if label == "Released":
                text = text[:10]

            facts.add_row(label, text)

    selection = [at(item, "item") for item in items(data.get("items"))]

    if selection:
        durations = [
            duration
            for item in selection
            if isinstance(duration := at(item, "duration").get("total_milliseconds"), int)
        ]

        facts.add_row("Loaded items", str(len(selection)))

        if durations:
            facts.add_row(
                "Loaded duration", f"{sum(durations) // 60000} min ({len(durations)} timed items)"
            )

    content: list[Text | Table] = [facts]
    description = value.get("description") or at(value, "profile", "biography").get("text")

    if description:
        content.extend((Text("\nABOUT", style="bold #1ED760"), Text(clean(description))))

    sections = {
        "Contributors": items(at(data, "credits").get("contributors")),
        "On this album": [
            at(item, "track") for item in items(at(data, "album", "tracks_v2").get("items"))
        ],
        "Releases": items(data.get("releases")),
        "On this playlist": [at(item, "item") for item in items(data.get("items"))],
        "Public playlists": items(value.get("public_playlists")),
        "Track listing": [
            at(item, "track")
            for item in items((at(value, "tracks_v2") or at(value, "tracks")).get("items"))
        ],
    }

    for heading, rows in sections.items():
        if not rows:
            continue

        table = Table.grid(padding=(0, 2))

        table.add_column(style="dim", width=3)
        table.add_column()
        table.add_column(style="dim")

        for index, row in enumerate(rows[:24], 1):
            label = clean(row.get("name")) or "Unavailable"
            extra = clean(row.get("role") or at(row, "date").get("year"))

            if not extra and isinstance(
                duration := at(row, "duration").get("total_milliseconds"), int
            ):
                seconds = duration // 1000
                extra = f"{seconds // 60}:{seconds % 60:02}"

            attributes = at(row, "playlist_audio_attributes")

            if isinstance(bpm := attributes.get("bpm"), (int, float)):
                extra = f"{bpm:.0f} BPM  " + extra

            if key := at(attributes, "key", "camelot_key").get("value"):
                extra = clean(key) + "  " + extra

            table.add_row(f"{index:02}", label, extra)

        content.extend((Text(f"\n{heading.upper()}", style="bold #1ED760"), table))

    primary = Group(*content)
    secondary = context(value, data)

    if secondary is None:
        return primary

    return Group(
        Columns(
            [
                Panel(primary, title="THE DETAILS", border_style="#293c33", padding=(1, 2)),
                Panel(secondary, title="EXPLORE FURTHER", border_style="#293c33", padding=(1, 2)),
            ],
            equal=True,
            expand=True,
            width=46,
        )
    )


def context(value: Mapping[str, Any], data: Mapping[str, Any]) -> Group | None:
    artist = at(data, "artist") or (value if "profile" in value else {})
    sections: list[Text | Table] = []
    stats = at(artist, "stats")

    if stats and "track" in data:
        sections.append(Text("ARTIST REACH", style="bold #1ED760"))

        for key, label in (
            ("monthly_listeners", "Monthly listeners"),
            ("followers", "Followers"),
            ("world_rank", "World ranking"),
        ):
            if isinstance(number := stats.get(key), int):
                sections.append(Text(f"{number:,}  {label}", style="bold white"))

    cities = items(at(stats, "top_cities").get("items"))
    top_tracks = [
        at(item, "track") for item in items(at(artist, "discography", "top_tracks").get("items"))
    ]
    neighbors = items(at(artist, "related_content", "related_artists").get("items"))

    for heading, rows in (
        ("Where they listen", cities),
        ("Popular tracks", top_tracks),
        ("Explore related artists", neighbors),
    ):
        if not rows:
            continue

        sections.append(Text("\n" + heading.upper(), style="bold #1ED760"))

        table = Table.grid(padding=(0, 2), expand=True)

        table.add_column(ratio=3)
        table.add_column(justify="right", style="dim", ratio=1)

        for row in rows[:20]:
            name = row.get("name") or row.get("city") or at(row, "profile").get("name")
            count = row.get("playcount") or row.get("number_of_listeners")
            duration = at(row, "duration").get("total_milliseconds")
            detail = f"{int(str(count)):,}" if str(count).isdigit() else ""

            if not detail and isinstance(duration, int):
                seconds = duration // 1000
                detail = f"{seconds // 60}:{seconds % 60:02}"

            table.add_row(clean(name), detail)

        sections.append(table)

    biography = at(artist, "profile", "biography").get("text")

    if biography and "track" in data:
        sections.extend((Text("\nTHE ARTIST", style="bold #1ED760"), Text(clean(biography))))

    return Group(*sections) if sections else None
