"""Cookie-authenticated account requests with Spotify's CSRF handshake."""

from __future__ import annotations

import json
from collections.abc import Mapping
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urlsplit

import wreq

from .client import AsyncClient
from .connection import Response
from .connection.types import Methods
from .playback import mapping
from .types import BaseClientError, HTTPError


class AccountPage(HTMLParser):
    __slots__ = (
        "csrf",
        "_reading",
        "_script",
        "data",
    )

    def __init__(self, html: str) -> None:
        """Initialize the account page parser or its borrowed cookie/CSRF session."""
        super().__init__()
        self.csrf: str | None = None
        self._reading = False
        self._script: list[str] = []
        self.feed(html)
        self.data: Mapping[str, Any] = (
            mapping(json.loads("".join(self._script))) if self._script else {}
        )

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Capture data-csrf and the account page's embedded JSON script."""
        attributes = dict(attrs)
        self.csrf = attributes.get("data-csrf") or self.csrf
        if tag == "script" and attributes.get("id") == "__NEXT_DATA__":
            self._reading = True

    def handle_endtag(self, tag: str) -> None:
        """Stop collecting embedded JSON at the end of its script."""
        if tag == "script":
            self._reading = False

    def handle_data(self, data: str) -> None:
        """Collect only the selected account-state script contents."""
        if self._reading:
            self._script.append(data)


class AccountSession:
    """Borrow a client and retain only the account page's CSRF state."""

    __slots__ = (
        "client",
        "page",
        "locale",
        "csrf",
        "origin",
    )

    def __init__(self, client: AsyncClient, page: str, *, locale: str = "en_US") -> None:
        """Initialize the account page parser or its borrowed cookie/CSRF session."""
        self.client = client
        self.page = page
        self.locale = locale
        self.csrf: str | None = None
        parsed = urlsplit(page)
        self.origin = f"{parsed.scheme}://{parsed.netloc}"

    async def prepare(self, url: str | None = None) -> AccountPage:
        """Fetch an account page and replace the CSRF token from its headers or state."""
        response = await self.client.get(
            url or self.page,
            headers={"accept-language": self.locale.replace("_", "-")},
            max_attempts=1,
        )
        page = AccountPage(response.text)
        props = mapping(page.data.get("props"))
        data = mapping(props.get("pageProps"))
        self.csrf = (
            response.headers.get("x-csrf-token")
            or page.csrf
            or props.get("csrfToken")
            or data.get("csrf")
        )

        if not isinstance(self.csrf, str) or not self.csrf:
            raise BaseClientError("Spotify's account page returned no CSRF token")
        return page

    async def request(
        self,
        method: Methods,
        path: str,
        *,
        body: Mapping[str, Any] | None = None,
        csrf: bool = True,
    ) -> Response:
        """Send an account request; retry once only when Spotify supplies a new CSRF token."""
        if csrf and self.csrf is None:
            await self.prepare()

        for attempt in range(2):
            headers = {
                "accept": "application/json",
                "accept-language": self.locale.replace("_", "-"),
                "origin": self.origin,
                "referer": self.page,
            }
            sent_token = self.csrf
            if sent_token:
                headers["x-csrf-token"] = sent_token

            request: wreq.Request = {"headers": headers}
            if body is not None:
                request["json"] = body
            response = await self.client.protocols.http.request(
                method, self.origin + path, max_attempts=1, **request
            )
            replacement = response.headers.get("x-csrf-token")
            if replacement:
                self.csrf = replacement

            status = response.status_code.as_int()
            if (
                attempt == 0
                and status in {400, 401, 403}
                and replacement
                and replacement != sent_token
            ):
                continue

            if not response.ok:
                raise HTTPError(
                    f"Spotify account request failed (HTTP {status})",
                    status_code=status,
                    response=response,
                )
            if "text/html" in response.headers.get("content-type", ""):
                raise HTTPError(
                    "Spotify returned an account login page", status_code=401, response=response
                )
            return response

        raise AssertionError("CSRF retry did not return a response")
