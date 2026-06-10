from __future__ import annotations

import threading
import atexit
import json
import time
import signal
import traceback
from typing import Any, Dict
from spotapi.login import Login
from spotapi.client import BaseClient
from spotapi.exceptions import WebSocketError
from spotapi.types.annotations import enforce
from websockets.sync.client import connect
from spotapi.utils.strings import random_hex_string

__all__ = ["WebsocketStreamer", "WebSocketError"]


@enforce
class WebsocketStreamer:
    """
    Standard streamer to connect to Spotify's websocket API.

    Parameters
    ----------
    login : Login
        The login object to use for authentication.
    """

    __slots__ = (
        "base",
        "client",
        "device_id",
        "ws",
        "rlock",
        "ws_dump",
        "connection_id",
        "keep_alive_thread",
        "supervisor_thread",
    )

    def __init__(self, login: Login) -> None:
        if not login.logged_in:
            raise ValueError("Must be logged in")
        
        self.login = login

        self.device_id = random_hex_string(32)

        self.rlock = threading.Lock()
        self.ws_dump = None
        self.ws = None
        self.connect()

        self.keep_alive_thread = threading.Thread(
            target=self.keep_alive,
            daemon=True,
        )
        self.keep_alive_thread.start()


        self.supervisor_thread = threading.Thread(
            target=self._supervise,
            daemon=True,
        )
        self.supervisor_thread.start()

        try:
            signal.signal(signal.SIGINT, self.handle_interrupt)
        except ValueError:  #< Not running in the main thread
            pass
        
        def _cleanup():
            print("Websockets closing due to program ending")
            self.disconnect()
        atexit.register(_cleanup)

    def _create_websocket(self) -> None:
        uri = f"wss://dealer.spotify.com/?access_token={self.base.access_token}"

        self.ws = connect(
            uri,
            user_agent_header=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )

        self.connection_id = self.get_init_packet()
    
    def connect(self):
        with self.rlock:
            self.base = BaseClient(self.login.client)
            self.client = self.base.client

            self.base.get_session()
            self.base.get_client_token()

            self._create_websocket()

            self.register_device()

    def disconnect(self):
        with self.rlock:
            if self.ws == None:
                return
            try:
                self.ws.close()
                self.ws = None
            except Exception as e:
                print(f"Failed to close websocket: {e}")

    def reconnect(self) -> None:
        self.disconnect()
        self.connect()

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
            try:
                print("\nREGISTER DEVICE FAILED")
                print(f"device_id     = {self.device_id}")
                print(f"connection_id = {self.connection_id}")
                print(f"error         = {resp.error.string}")
                print(f"response      = {resp.response}")
            except Exception:
                pass

            raise WebSocketError(
                "Could not register device",
                error=resp.error.string
            )

    def connect_device(self) -> Dict[str, Any]:
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
            try:
                print("\nCONNECT DEVICE FAILED")
                print(f"device_id     = {self.device_id}")
                print(f"connection_id = {self.connection_id}")
                print(f"error         = {resp.error.string}")
                print(f"response      = {resp.response}")
            except Exception:
                pass

            raise WebSocketError(
                "Could not connect device",
                error=resp.error.string
            )

        return resp.response

    def keep_alive(self) -> None:
        while True:
            try:
                time.sleep(60)

                with self.rlock:
                    self.ws.send('{"type":"ping"}')

            except Exception as e:
                print("Websocket disconnected, reconnecting...")

                try:
                    self.reconnect()
                except Exception as reconnectError:
                    print(f"Reconnect failed: {reconnectError}")
                time.sleep(5)

    def get_packet(self):
        while True:
            try:
                ws_dump = dict(json.loads(self.ws.recv()))

                self.ws_dump = ws_dump
                return ws_dump

            except Exception:
                try:
                    self.reconnect()
                except Exception as e:
                    print("Failed to reconnect!")

                time.sleep(1)

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
        print("Ctrl+C detected, exiting spotapi")
        self.disconnect()
        exit(0)

    def _supervise(self) -> None:
        """Monitor websocket and threads, attempt reconnects when down."""
        backoff = 1
        while True:
            try:
                need_reconnect = False

                if self.ws == None:
                    need_reconnect = True
                else:
                    try:
                        closed_attr = self.ws.closed
                        if closed_attr is True:
                            need_reconnect = True
                    except Exception:
                        need_reconnect = True

                if need_reconnect:
                    try:
                        self.reconnect()
                        backoff = 1
                    except Exception as e:
                        print(f"Spotapi failed to reconnect: {e}")
                        traceback.print_exc()
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 60)

                time.sleep(5)
            except Exception:
                time.sleep(5)
