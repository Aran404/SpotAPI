from __future__ import annotations
from websockets.sync.client import connect
from spotapi.utils.strings import random_hex_string
from spotapi.login import Login
from spotapi.client import BaseClient
from spotapi.exceptions import WebSocketError
from typing import Any
import threading
import atexit
import json
import time
import signal


class WebsocketStreamer:
    """
    Standard streamer to connect to Spotify's websocket API.
    """

    def __init__(self, login: Login) -> None:
        if not login.logged_in:
            raise ValueError("Must be logged in")

        self.base = BaseClient(login.client)
        self.client = self.base.client

        self.base.get_session()
        self.base.get_client_token()

        self.device_id = random_hex_string(32)

        uri = f"wss://gue1-dealer2.spotify.com/?access_token={self.base.access_token}"
        self.ws = connect(
            uri,
            user_agent_header="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        self.rlock = threading.Lock()
        self.ws_dump: dict | None = None
        self.connection_id = self.get_init_packet()

        self.keep_alive_thread = threading.Thread(target=self.keep_alive, daemon=True)
        self.keep_alive_thread.start()

        atexit.register(self.ws.close)
        signal.signal(signal.SIGINT, self.handle_interrupt)

    def register_device(self) -> None:
        url = f"https://gue1-spclient.spotify.com/track-playback/v1/devices"
        payload = {
            "device": {
                "brand": "spotify",
                "capabilities": {
                    "change_volume": True,
                    "enable_play_token": True,
                    "supports_file_media_type": True,
                    "play_token_lost_behavior": "pause",
                    "disable_connect": False,
                    "audio_podcasts": True,
                    "video_playback": True,
                    "manifest_formats": [
                        "file_ids_mp3",
                        "file_urls_mp3",
                        "manifest_urls_audio_ad",
                        "manifest_ids_video",
                        "file_urls_external",
                        "file_ids_mp4",
                        "file_ids_mp4_dual",
                        "manifest_urls_audio_ad",
                    ],
                },
                "device_id": self.device_id,
                "device_type": "computer",
                "metadata": {},
                "model": "web_player",
                "name": "Web Player (Chrome)",
                "platform_identifier": "web_player windows 10;chrome 120.0.0.0;desktop",
                "is_group": False,
            },
            "outro_endcontent_snooping": False,
            "connection_id": self.connection_id,
            "client_version": "harmony:4.43.2-a61ecaf5",
            "volume": 65535,
        }

        resp = self.client.post(url, json=payload, authenticate=True)

        if resp.fail:
            raise WebSocketError("Could not register device", error=resp.error.string)

    def connect_device(self) -> dict[str, Any]:
        url = f"https://gue1-spclient.spotify.com/connect-state/v1/devices/hobs_{self.device_id}"
        payload = {
            "member_type": "CONNECT_STATE",
            "device": {
                "device_info": {
                    "capabilities": {
                        "can_be_player": False,
                        "hidden": True,
                        "needs_full_player_state": True,
                    }
                }
            },
        }
        headers = {
            "x-spotify-connection-id": self.connection_id,
        }

        resp = self.client.put(url, json=payload, authenticate=True, headers=headers)

        if resp.fail:
            raise WebSocketError("Could not connect device", error=resp.error.string)

        return resp.response

    def keep_alive(self) -> None:
        while True:
            try:
                time.sleep(60)
                with self.rlock:
                    self.ws.send('{"type":"ping"}')
            except (ConnectionError, KeyboardInterrupt):
                break

    def get_packet(self) -> dict:
        with self.rlock:
            ws_dump = dict(json.loads(self.ws.recv()))
            self.ws_dump = ws_dump
            return self.ws_dump

    def get_init_packet(self) -> str:
        """Gets the Spotify Connection ID in the init packet"""
        packet = self.get_packet()

        if (
            packet.get("headers") is None
            or dict(packet["headers"]).get("Spotify-Connection-Id") is None
        ):
            raise ValueError("Invalid init packet")

        return packet["headers"]["Spotify-Connection-Id"]

    def handle_interrupt(self, signum: int, frame: Any) -> None:
        """Handle interrupt signal (Ctrl+C)"""
        self.ws.close()
        exit(0)
