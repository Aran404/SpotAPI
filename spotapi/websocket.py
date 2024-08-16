from __future__ import annotations
from websockets.sync.client import connect
from spotapi.login import Login
from spotapi.client import BaseClient
from typing import Optional
import threading
import atexit
import json
import time


class WebsocketStreamer(BaseClient, Login):
    """
    Standard streamer to connect to spotify's websocket API.
    """

    def __new__(cls, login: Login) -> WebsocketStreamer:
        instance = super().__new__(cls)
        instance.__dict__.update(login.__dict__)
        return instance

    def __init__(self, login: Login, ignore_init_packet: Optional[bool] = True):
        if not login.logged_in:
            raise ValueError("Must be logged in")

        super().__init__(client=login.client)

        self.get_session()
        self.get_client_token()

        uri = f"wss://gue1-dealer2.spotify.com/?access_token={self.access_token}"
        self.ws = connect(
            uri,
            user_agent_header="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )

        self.rlock = threading.Lock()
        self.ws_dump: dict | None = None

        if ignore_init_packet:
            self.get_init_packet()

        threading.Thread(target=self.keep_alive, daemon=True).start()
        atexit.register(self.ws.close)

    def keep_alive(self) -> None:
        while True:
            # We need to make sure the ws doesn't read the PONG
            with self.rlock:
                self.ws.send('{"type":"ping"}')
                self.ws.recv()

            time.sleep(60)

    def get_packet(self) -> dict:
        with self.rlock:
            self.ws_dump = dict(json.loads(self.ws.recv()))
            return self.ws_dump

    def get_main_packet(self) -> dict:
        """Eqivalent to get_packet() just asserts that the init packet has been consumed"""
        with self.rlock:
            self.ws_dump = dict(json.loads(self.ws.recv()))

            is_not_init_packet: bool = (self.ws_dump.get("headers") is None) or (
                dict(self.ws_dump["headers"]).get("Spotify-Connection-Id") is None
            )
            assert (
                not is_not_init_packet
            ), "Init packet has not been consumed yet, restart the streamer."

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

    def get_player_state(self) -> dict:
        self.get_main_packet()
        payload = self.ws_dump["payload"][0]
        return payload["cluster"]["player_state"]
