import asyncio
import time
import os
from dotenv import load_dotenv

from spotapi.v2.public import Public
from spotapi.v2.types import LoggerColour


# ANSI Escape Codes for Terminal Aesthetics
class TUI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"

    # Custom Colors
    SPOTIFY_GREEN = "\033[38;2;30;215;96m"  # Exact Spotify Hex #1ED760
    CYAN = "\033[38;2;0;255;255m"
    MAGENTA = "\033[38;2;255;0;255m"
    YELLOW = "\033[38;2;255;215;0m"
    BLUE = "\033[38;2;100;149;237m"
    WHITE = "\033[38;2;255;255;255m"


def print_header(title: str, icon: str, color: str) -> None:
    """Prints a styled header for distinct visual sections."""
    divider = "━" * 40
    print(f"\n{color}{TUI.BOLD} {icon} {title.upper()} {divider}{TUI.RESET}")


async def main() -> None:
    load_dotenv()
    logr = LoggerColour()

    # Launch Banner
    print(f"\n{TUI.SPOTIFY_GREEN}{TUI.BOLD}🚀 INITIATING CONCURRENT SPOTIFY SEARCH...{TUI.RESET}")
    print(
        f"{TUI.DIM}Fetching Playlists, Tracks, Albums, Podcasts, and Artists in parallel.{TUI.RESET}\n"
    )

    start_time = time.time_ns()

    # 1. Define Coroutines
    coro1 = anext(Public.search_playlists("Juice Wrld"))
    coro2 = anext(Public.search_tracks("Lady Gaga"))
    coro3 = anext(Public.search_albums("Hello World"))
    coro4 = anext(Public.search_podcasts("mayweather"))
    coro5 = anext(Public.search_artists("Ferocious"))

    # 2. Run Concurrently
    playlists, tracks, albums, podcasts, artists = await asyncio.gather(
        coro1, coro2, coro3, coro4, coro5
    )

    # 3. Format and Display Results (Limited to top 5 for a clean SVG)
    MAX_ITEMS = 5

    print_header("Playlists", "🎶", TUI.CYAN)
    for i, t in enumerate(playlists):
        if i == MAX_ITEMS:
            break
        logr.info(
            f"{TUI.DIM}[{i+1}]{TUI.RESET} {TUI.CYAN}{TUI.BOLD}{t.name}{TUI.RESET} {TUI.DIM}→{TUI.RESET} {t.uri}"
        )

    print_header("Tracks", "🎵", TUI.MAGENTA)
    for i, t in enumerate(tracks):
        if i == MAX_ITEMS:
            break
        logr.info(
            f"{TUI.DIM}[{i+1}]{TUI.RESET} {TUI.MAGENTA}{TUI.BOLD}{t.name}{TUI.RESET} {TUI.DIM}→ Album ID:{TUI.RESET} {t.album_of_track.id}"
        )

    print_header("Albums", "💿", TUI.YELLOW)
    for i, t in enumerate(albums):
        if i == MAX_ITEMS:
            break
        logr.info(
            f"{TUI.DIM}[{i+1}]{TUI.RESET} {TUI.YELLOW}[{t.type.upper()}]{TUI.RESET} {TUI.BOLD}{t.name}{TUI.RESET} {TUI.DIM}→{TUI.RESET} {t.uri}"
        )

    print_header("Podcasts", "🎙️", TUI.SPOTIFY_GREEN)
    for i, t in enumerate(podcasts):
        if i == MAX_ITEMS:
            break
        logr.info(f"{TUI.DIM}[{i+1}]{TUI.RESET} {TUI.SPOTIFY_GREEN}{TUI.BOLD}{t.name}{TUI.RESET}")

    print_header("Artists", "🎤", TUI.BLUE)
    for i, t in enumerate(artists):
        if i == MAX_ITEMS:
            break
        # Assuming t.name is available, combining it with t.uri for better context
        name = t.profile.name
        logr.info(
            f"{TUI.DIM}[{i+1}]{TUI.RESET} {TUI.BLUE}{TUI.BOLD}{name}{TUI.RESET} {TUI.DIM}→{TUI.RESET} {t.uri}"
        )

    # 4. Execution Time Footer
    elapsed_sec = (time.time_ns() - start_time) / 1e9
    print(
        f"\n{TUI.SPOTIFY_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{TUI.RESET}"
    )
    logr.info(
        f"✨ {TUI.BOLD}Search completed concurrently in {TUI.WHITE}{elapsed_sec:.4f} seconds{TUI.RESET}"
    )
    print(
        f"{TUI.SPOTIFY_GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{TUI.RESET}\n"
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print(f"\n{TUI.DIM}Process aborted by user.{TUI.RESET}")
