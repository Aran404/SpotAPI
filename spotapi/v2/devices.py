"""Scoped track-playback registrations, independent of Connect observers."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import Mapping
from typing import Any, Self
from urllib.parse import quote
from uuid import uuid4

from .playback import integer
from .session import AuthSession
from .types import BaseClientError

PLAYBACK_URL = "https://spclient.wg.spotify.com"


class RegisteredDevice:
    """Register your renderer with ``create()``, then close it or use its context."""

    def __init__(
        self, session: AuthSession, device_id: str, *, endpoint: str = PLAYBACK_URL
    ) -> None:
        """Describe an owned playback registration without making a request."""
        self.session = session
        self.id = device_id
        self.keep_alive_seconds = 0
        self.supports_observing = False

        self._url = endpoint + "/track-playback/v1/devices/" + quote(device_id, safe="")
        self._sequence = 1
        self._closed = False
        self._lock = asyncio.Lock()

    @classmethod
    async def create(
        cls,
        session: AuthSession,
        *,
        connection_id: str,
        name: str,
        client_version: str,
        platform_identifier: str,
        capabilities: Mapping[str, Any],
        device_id: str | None = None,
        endpoint: str = PLAYBACK_URL,
    ) -> Self:
        """Register a device tied to the active dealer connection."""
        if not name.strip() or not client_version.strip() or not platform_identifier.strip():
            raise ValueError("Name, client version and platform identifier are required")

        registration = cls(session, device_id or secrets.token_hex(20), endpoint=endpoint)
        payload = {
            "device": {
                "brand": "spotify",
                "device_id": registration.id,
                "device_type": "computer",
                "name": name,
                "model": "web_player",
                "platform_identifier": platform_identifier,
                "correlation_id": str(uuid4()),
                "metadata": {},
                "is_group": False,
                "is_public": False,
                "capabilities": dict(capabilities),
                "client_version": client_version,
            },
            "connection_id": connection_id,
            "client_version": client_version,
            "outro_endcontent_snooping": False,
            "volume": 65535,
        }

        try:
            response = await session.client.post(
                endpoint + "/track-playback/v1/devices",
                headers=session.authorized_headers,
                json=payload,
                max_attempts=1,
            )
            body = response.json
            sequence = integer(body.get("initial_seq_num"), -1) if body else -1

            if sequence < 0:
                raise BaseClientError("Spotify returned no initial device sequence number")

            registration._sequence = sequence
            registration.keep_alive_seconds = (
                integer(body.get("device_keep_alive_update_seconds")) if body else 0
            )
            registration.supports_observing = bool(body and body.get("supports_observing") is True)
        except BaseException as error:
            try:
                await registration.close()
            except Exception as cleanup:
                raise error from cleanup

            raise

        return registration

    async def __aenter__(self) -> Self:
        """Enter this resource's asynchronous ownership scope."""
        if self._closed:
            raise RuntimeError("Device registration is closed")

        return self

    async def __aexit__(
        self, _type: object, error: BaseException | None, _traceback: object
    ) -> None:
        """Release resources owned by this asynchronous scope."""
        try:
            await self.close()
        except Exception as cleanup:
            if error is not None:
                raise error from cleanup

            raise

    async def report(
        self,
        *,
        state_ref: Mapping[str, Any] | None,
        sub_state: Mapping[str, Any],
        debug_source: str,
    ) -> None:
        """Report renderer state once with the next monotonic sequence number."""
        async with self._lock:
            if self._closed:
                raise RuntimeError("Device registration is closed")

            self._sequence += 1
            payload = {
                "seq_num": self._sequence,
                "state_ref": state_ref,
                "sub_state": dict(sub_state),
                "debug_source": debug_source,
            }

            await self.session.client.put(
                self._url + "/state",
                headers=self.session.authorized_headers,
                json=payload,
                max_attempts=1,
            )

    async def close(self, *, seq_num: int | None = None) -> None:
        """Deregister this owned device; retain errors when Spotify refuses cleanup."""
        async with self._lock:
            if self._closed:
                return

            sequence = self._sequence + 1 if seq_num is None else seq_num

            if type(sequence) is not int or sequence < 0:
                raise ValueError("seq_num must be a non-negative integer")

            response = await self.session.client.protocols.http.delete(
                self._url,
                headers=self.session.authorized_headers,
                max_attempts=1,
                json={
                    "seq_num": sequence,
                    "state_ref": None,
                    "sub_state": {
                        "playback_speed": 1,
                        "format": "file_urls_external",
                        "is_video_on": False,
                    },
                    "debug_source": "deregister",
                },
            )

            if not response.ok and response.status_code.as_int() != 404:
                raise BaseClientError(
                    f"Could not remove playback device: HTTP {response.status_code.as_int()}"
                )

            self._closed = True
