"""Read-only Spotify import and bounded candidate retrieval."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import aclosing
from dataclasses import dataclass, replace

from spotapi import Catalogue, Library, LikedTracks, LoginExpired
from spotapi.models.catalogue import Track
from spotapi.models.catalogue.album_details import AlbumTrack
from spotapi.models.catalogue.artist_details import ArtistDetails
from spotapi.models.catalogue.playlist_track import PlaylistTrack
from spotapi.session import AuthSession
from spotapi.types import SpotAPIError

from .engine import Taste
from .models import Candidate, Seed, Song
from .store import Store


@dataclass(frozen=True, slots=True)
class ImportResult:
    tracks: int
    playlists: int
    albums: int
    failures: tuple[str, ...]


def song_from_track(track: Track | PlaylistTrack | AlbumTrack) -> Song:
    artists = track.artists.items if track.artists else ()
    duration = track.duration.total_milliseconds if track.duration else 0
    return Song(
        track.uri,
        track.name,
        tuple(artist.uri for artist in artists),
        tuple(artist.profile.name if artist.profile else "" for artist in artists),
        duration,
        bpm=track.bpm if isinstance(track, PlaylistTrack) else None,
    )


async def _library_resources(session: AuthSession) -> dict[str, str]:
    library = Library(session)
    pending: list[str | None] = [None]
    visited: set[str | None] = set()
    resources: dict[str, str] = {}
    while pending:
        folder = pending.pop()
        if folder in visited:
            continue

        visited.add(folder)
        async with aclosing(library.pages(folder=folder)) as pages:
            async for page in pages:
                for item in page.items:
                    if item.kind == "folder":
                        pending.append(item.uri)
                    elif item.kind in {"playlist", "album"}:
                        resources[item.uri] = item.kind

    return resources


async def _read_resource(catalogue: Catalogue, uri: str, kind: str) -> list[Song]:
    songs: list[Song] = []
    if kind == "playlist":
        async with aclosing(catalogue.get_playlist_tracks(uri)) as playlists:
            async for playlist in playlists:
                songs.extend(song_from_track(track) for track in playlist)
    else:
        async with aclosing(catalogue.get_album_tracks(uri)) as albums:
            async for album in albums:
                songs.extend(song_from_track(track) for track in album)

    return songs


async def sync_library(
    catalogue: Catalogue, session: AuthSession, store: Store, progress: Callable[[str], None]
) -> ImportResult:
    """Import all accessible liked songs, saved playlists, nested folders, and albums."""
    liked: list[Song] = []
    async with aclosing(LikedTracks(session).pages()) as pages:
        async for page in pages:
            for saved in page:
                liked.append(
                    song_from_track(saved.track)
                    if saved.track is not None
                    else Song(saved.uri, saved.uri, (), ())
                )
    await asyncio.to_thread(store.replace_source, "liked", liked, 2.0)
    progress(f"Imported {len(liked)} liked-track records")

    resources = await _library_resources(session)
    current = {"liked"}
    failures: list[str] = []
    tracks, playlists, albums = len(liked), 0, 0
    for index, (uri, kind) in enumerate(resources.items(), 1):
        source = kind + ":" + uri
        current.add(source)
        try:
            songs = await _read_resource(catalogue, uri, kind)
            await asyncio.to_thread(store.replace_source, source, songs, 0.75)
            tracks += len(songs)
            playlists += kind == "playlist"
            albums += kind == "album"
            progress(f"Imported saved {kind} {index}/{len(resources)} ({len(songs)} tracks)")
        except LoginExpired:
            raise
        except (SpotAPIError, ValueError, TimeoutError) as error:
            failures.append(f"Saved {kind} {index}: {type(error).__name__}")

    if not failures:
        await asyncio.to_thread(store.remove_stale_sources, current)

    return ImportResult(tracks, playlists, albums, tuple(failures))


def _top_songs(artist: ArtistDetails) -> list[Song]:
    top = artist.discography.top_tracks if artist.discography else None
    population = artist.stats.monthly_listeners if artist.stats else None
    return [
        Song(
            item.track.uri,
            item.track.name,
            (artist.uri,),
            (artist.name,),
            item.track.duration.total_milliseconds if item.track.duration else 0,
            population,
        )
        for item in (top.items if top else ())
    ]


async def _artist_songs(
    catalogue: Catalogue, artist: ArtistDetails
) -> tuple[list[Song], str | None]:
    songs = _top_songs(artist)
    discography = artist.discography
    groups = discography.albums.items if discography and discography.albums else ()
    releases = [release for group in groups for release in group.releases.items]
    try:
        if releases:
            async with aclosing(catalogue.get_album_tracks(releases[0].uri, limit=20)) as pages:
                for track in await anext(pages, ()):
                    song = song_from_track(track)
                    if song.artists and song.artists[0] == artist.uri and artist.stats:
                        song = replace(song, monthly_listeners=artist.stats.monthly_listeners)
                    songs.append(song)
    except LoginExpired:
        raise
    except (SpotAPIError, ValueError, TimeoutError) as error:
        return songs, "Album deep cuts: " + type(error).__name__

    return songs, None


async def retrieve(
    catalogue: Catalogue,
    seeds: tuple[Seed, ...],
    *,
    seed_artists: int = 8,
    neighbors: int = 5,
    progress: Callable[[str], None] = print,
) -> tuple[tuple[Candidate, ...], tuple[str, ...]]:
    if not 1 <= seed_artists <= 30 or not 1 <= neighbors <= 15:
        raise ValueError("Use 1-30 seed artists and 1-15 neighbors")

    weights = Taste.fit(seeds).artists
    favorites = sorted(weights, key=lambda artist: (-weights[artist], artist))[:seed_artists]
    links: dict[str, set[str]] = {artist: set() for artist in favorites}
    details: dict[str, ArtistDetails] = {}
    playlists: dict[str, set[str]] = {}
    failures: list[str] = []
    for index, artist in enumerate(favorites, 1):
        try:
            detail = await catalogue.get_artist(artist)
            details[artist] = detail
            related = await catalogue.get_related_artists(artist)
            for neighbor in related[:neighbors]:
                links.setdefault(neighbor.uri, set()).add(artist)
            progress(f"Mapped favorite artist {index}/{len(favorites)}")
        except LoginExpired:
            raise
        except (SpotAPIError, ValueError, TimeoutError) as error:
            failures.append(f"Seed artist {index}: {type(error).__name__}")

        try:
            discovered = await catalogue.get_artist_discovered_on(artist)
            for playlist in discovered:
                if playlist is not None:
                    playlists.setdefault(playlist.uri, set()).add(artist)
                    break
        except LoginExpired:
            raise
        except (SpotAPIError, ValueError, TimeoutError) as error:
            failures.append(f"Artist context {index}: {type(error).__name__}")

    candidates: dict[str, Candidate] = {}
    semaphore = asyncio.Semaphore(3)

    def add(song: Song, bridges: set[str]) -> None:
        previous = candidates.get(song.uri)
        merged = bridges | (set(previous.bridges) if previous else set[str]())
        if previous is not None:
            # Prefer richer credits deterministically, regardless of task completion order.
            choices = (song, previous.song)
            preferred = max(
                choices, key=lambda item: (len(item.artists), item.duration_ms, item.artists)
            )
            population = next(
                (
                    item.monthly_listeners
                    for item in choices
                    if item.artists[:1] == preferred.artists[:1]
                    and item.monthly_listeners is not None
                ),
                None,
            )
            song = replace(preferred, monthly_listeners=population)
        candidates[song.uri] = Candidate(song, tuple(sorted(merged)))

    async def fetch(artist: str, bridges: set[str]) -> None:
        async with semaphore:
            try:
                detail = details.get(artist) or await catalogue.get_artist(artist)
                songs, warning = await _artist_songs(catalogue, detail)
                if warning:
                    failures.append(warning)
                for song in songs:
                    add(song, bridges)
            except LoginExpired:
                raise
            except (SpotAPIError, ValueError, TimeoutError) as error:
                failures.append(f"Candidate artist {artist}: {type(error).__name__}")

    async def fetch_playlist(uri: str, bridges: set[str]) -> None:
        async with semaphore:
            try:
                async with aclosing(catalogue.get_playlist_tracks(uri, limit=50)) as pages:
                    for track in await anext(pages, ()):
                        add(song_from_track(track), bridges)
            except LoginExpired:
                raise
            except (SpotAPIError, ValueError, TimeoutError) as error:
                failures.append(f"Context playlist: {type(error).__name__}")

    async with asyncio.TaskGroup() as group:
        for artist, bridges in links.items():
            group.create_task(fetch(artist, bridges))
        for uri, bridges in playlists.items():
            group.create_task(fetch_playlist(uri, bridges))

    return tuple(candidates.values()), tuple(failures)
