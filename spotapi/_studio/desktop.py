"""A native WebView shell; only the local application receives a Python bridge."""

from __future__ import annotations

import asyncio
import os
import secrets
import threading
from collections.abc import Callable
from concurrent.futures import TimeoutError as FutureTimeout
from http.cookies import SimpleCookie
from importlib import import_module
from pathlib import Path
from typing import Any, Protocol, cast
from urllib.parse import urlsplit

from .service import Studio

_LOGIN_TIMEOUT = 40.0


class Window(Protocol):
    """The small native-window surface used by this example."""

    events: Any

    def get_current_url(self) -> str | None:
        """Return the currently displayed page URL."""
        ...

    def get_cookies(self) -> list[SimpleCookie]:
        """Read cookies from this window's own ephemeral browser session."""
        ...

    def evaluate_js(self, script: str) -> object:
        """Evaluate a fixed application notification, never a credential string."""
        ...

    def destroy(self) -> None:
        """Close this native window."""
        ...


class WebView(Protocol):
    """Keep the untyped optional GUI package behind an explicit boundary."""

    def create_window(self, title: str, url: str | None = None, **options: Any) -> Window:
        """Create a native application or isolated Spotify login window."""
        ...

    def start(self, func: Callable[[], None], **options: Any) -> None:
        """Run the native event loop on the main thread."""
        ...


def _authenticate(studio: Studio, loop: asyncio.AbstractEventLoop, cookie: str) -> bool:
    """Bound authentication and cancel its loop task when the native wait fails."""
    future = asyncio.run_coroutine_threadsafe(studio.authenticate(cookie), loop)
    try:
        future.result(timeout=_LOGIN_TIMEOUT)
    except Exception:
        future.cancel()
        return False
    return True


class Bridge:
    """Expose only named application operations, never clients, cookies or evaluation."""

    def __init__(
        self,
        studio: Studio,
        loop: asyncio.AbstractEventLoop,
        webview: WebView,
        notify: Callable[[str], None],
    ) -> None:
        """Bind UI requests to the owning asyncio loop and a private notification callback."""
        self._studio = studio
        self._loop = loop
        self._webview = webview
        self._notify = notify
        self._login: Window | None = None
        self._login_lock = threading.Lock()
        self._importing = False

    def request(self, action: object, values: object = None) -> dict[str, Any]:
        """Submit one command onto the library's owning asyncio loop."""
        if not isinstance(action, str) or not isinstance(values or {}, dict):
            return {"ok": False, "error": "Invalid application request"}
        payload = cast(dict[object, object], values or {})
        if any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in payload.items()
        ):
            return {"ok": False, "error": "Form values must be strings"}
        future = asyncio.run_coroutine_threadsafe(
            self._studio.request(action, cast(dict[str, str], payload)), self._loop
        )
        try:
            return future.result(timeout=50)
        except FutureTimeout:
            future.cancel()
            return {
                "ok": False,
                "error": "The request timed out; refresh before retrying a change",
            }

    def login(self) -> dict[str, object]:
        """Open Spotify's normal login in a window with no Python API exposed."""
        with self._login_lock:
            if self._login is not None:
                return {"ok": False, "error": "A Spotify sign-in window is already open"}
            login = self._webview.create_window(
                "Sign in to Spotify · SpotAPI Studio",
                "https://accounts.spotify.com/login?continue=https%3A%2F%2Fopen.spotify.com%2F",
                width=520,
                height=780,
            )
            self._login = login
            login.events.loaded += self._capture_login
            login.events.closed += self._login_closed
        return {"ok": True}

    def _login_closed(self) -> None:
        """Allow another explicit login after the user closes its window."""
        with self._login_lock:
            self._login = None

    def _capture_login(self) -> None:
        """Import only sp_dc after the user reaches Spotify's authenticated player."""
        with self._login_lock:
            login = self._login
            if login is None or self._importing:
                return
            self._importing = True
        try:
            if urlsplit(login.get_current_url() or "").hostname != "open.spotify.com":
                return
            cookie = next(
                (jar["sp_dc"].value for jar in login.get_cookies() if "sp_dc" in jar), None
            )
            if not cookie:
                return
            if not _authenticate(self._studio, self._loop, "sp_dc=" + cookie):
                self._notify("failed")
                return
            login.destroy()
            self._notify("signed_in")
        finally:
            with self._login_lock:
                self._importing = False


def page() -> str:
    """Assemble bundled assets with a fresh CSP nonce and no remote scripts or fonts."""
    root = Path(__file__).parent
    nonce = secrets.token_urlsafe(24)
    return (
        (root / "index.html")
        .read_text(encoding="utf-8")
        .replace("{{nonce}}", nonce)
        .replace(
            "<!-- STUDIO_LOGO -->",
            (root / "assets" / "logo.svg").read_text(encoding="utf-8"),
        )
        .replace("/* STUDIO_STYLE */", (root / "style.css").read_text(encoding="utf-8"))
        .replace("// STUDIO_SCRIPT", (root / "app.js").read_text(encoding="utf-8"))
    )


def main() -> None:
    """Launch Studio using an explicit .env session or a user-driven browser login."""
    from dotenv import load_dotenv

    load_dotenv(Path.cwd() / ".env")
    webview = cast(WebView, import_module("webview"))
    loop = asyncio.new_event_loop()
    studio = Studio()
    worker = threading.Thread(target=loop.run_forever, name="spotapi-studio", daemon=True)

    def notify(status: str) -> None:
        """Notify the page using fixed scripts with no embedded account values."""
        window.evaluate_js(
            "window.studio.signedIn()" if status == "signed_in" else "window.studio.loginFailed()"
        )

    bridge = Bridge(studio, loop, webview, notify)
    try:
        window = webview.create_window(
            "SpotAPI Studio",
            html=page(),
            js_api=bridge,
            width=1480,
            height=960,
            min_size=(980, 720),
            background_color="#121016",
            text_select=True,
        )
    except BaseException:
        loop.close()
        raise

    def initialize() -> None:
        """Load credentials in Python only and notify the already-rendered application."""
        cookie = os.getenv("SPOTIFY_COOKIE")
        if cookie:
            notify("signed_in" if _authenticate(studio, loop, cookie) else "failed")

    worker.start()
    try:
        icon = Path(__file__).parent / "assets" / ("logo.ico" if os.name == "nt" else "logo.png")
        webview.start(initialize, private_mode=True, icon=str(icon))
    finally:

        async def shutdown() -> None:
            """Cancel this GUI loop's in-flight work before closing borrowed resources."""
            current = asyncio.current_task()
            pending = [task for task in asyncio.all_tasks() if task is not current]
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            await studio.close()
            await loop.shutdown_asyncgens()
            await loop.shutdown_default_executor()

        try:
            asyncio.run_coroutine_threadsafe(shutdown(), loop).result(timeout=15)
        finally:
            loop.call_soon_threadsafe(loop.stop)
            worker.join(timeout=5)
            loop.close()


if __name__ == "__main__":
    main()
