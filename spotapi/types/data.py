from __future__ import annotations

from dataclasses import dataclass, field
from spotapi.http.request import TLSClient
from typing import List, Dict, Any, Union
from spotapi.types.interfaces import CaptchaProtocol, LoggerProtocol

__all__ = [
    "Config",
    "SolverConfig",
    "Metadata",
    "Track",
    "Index",
    "PlayOrigin",
    "Restrictions",
    "Options",
    "PlaybackQuality",
    "ContextMetadata",
    "PlayerState",
    "Hifi",
    "AudioOutputDeviceInfo",
    "Capabilities",
    "MetadataMap",
    "Device",
    "Devices",
]


@dataclass
class Config:
    logger: LoggerProtocol
    solver: CaptchaProtocol | None = field(default=None)
    client: TLSClient = field(default=TLSClient("chrome_120", "", auto_retries=3))

    def __str__(self) -> str:
        return "Config()"


@dataclass
class SolverConfig:
    api_key: str
    captcha_service: str
    retries: int = field(default=120)

    def __str__(self) -> str:
        return "SolverConfig()"


@dataclass
class Metadata:
    ORIGINAL_SESSION_ID: str | None = None
    album_title: str | None = None
    image_xlarge_url: str | None = None
    actions_skipping_next_past_track: str | None = None
    interaction_id: str | None = None
    title: str | None = None
    artist_uri: str | None = None
    image_url: str | None = None
    entity_uri: str | None = None
    image_large_url: str | None = None
    iteration: str | None = None
    actions_skipping_prev_past_track: str | None = None
    page_instance_id: str | None = None
    album_uri: str | None = None
    image_small_url: str | None = None
    track_player: str | None = None
    context_uri: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metadata":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "Metadata()"


@dataclass
class Track:
    uri: str | None = None
    uid: str | None = None
    metadata: Metadata | None = None
    provider: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track":
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            data["metadata"] = Metadata.from_dict(metadata)
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "Track()"


@dataclass
class Index:
    page: int | None = None
    track: int | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Index":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "Index()"


@dataclass
class PlayOrigin:
    feature_identifier: str | None = None
    feature_version: str | None = None
    referrer_identifier: str | None = None
    device_identifier: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayOrigin":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "PlayOrigin()"


@dataclass
class Restrictions:
    disallow_resuming_reasons: List[str] = field(default_factory=list)
    disallow_setting_playback_speed_reasons: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Restrictions":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "Restrictions()"


@dataclass
class Options:
    shuffling_context: bool | None = None
    repeating_context: bool | None = None
    repeating_track: bool | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Options":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "Options()"


@dataclass
class PlaybackQuality:
    bitrate_level: str | None = None
    strategy: str | None = None
    target_bitrate_level: str | None = None
    target_bitrate_available: bool | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaybackQuality":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "PlaybackQuality()"


@dataclass
class ContextMetadata:
    image_url: str | None = None
    context_description: str | None = None
    context_owner: str | None = None
    playlist_number_of_tracks: str | None = None
    playlist_number_of_episodes: str | None = None
    player_arch: str | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextMetadata":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "ContextMetadata()"


@dataclass
class PlayerState:
    timestamp: str | None = None
    context_uri: str | None = None
    context_url: str | None = None
    context_restrictions: Dict[str, str] = field(default_factory=dict)
    play_origin: PlayOrigin | None = None
    index: Index | None = None
    track: Track | None = None
    playback_id: str | None = None
    playback_speed: float | None = None
    position_as_of_timestamp: str | None = None
    duration: str | None = None
    is_playing: bool | None = None
    is_paused: bool | None = None
    is_system_initiated: bool | None = None
    options: Options | None = None
    restrictions: Restrictions | None = None
    suppressions: Dict[str, str] = field(default_factory=dict)
    prev_tracks: List[Track] = field(default_factory=list)
    next_tracks: List[Track] = field(default_factory=list)
    context_metadata: ContextMetadata | None = None
    page_metadata: Dict[str, str] = field(default_factory=dict)
    session_id: str | None = None
    queue_revision: str | None = None
    playback_quality: PlaybackQuality | None = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayerState":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        if "play_origin" in valid_keys:
            valid_keys["play_origin"] = PlayOrigin.from_dict(
                valid_keys.get("play_origin", {})
            )
        if "index" in valid_keys:
            valid_keys["index"] = Index.from_dict(valid_keys.get("index", {}))
        if "track" in valid_keys:
            valid_keys["track"] = Track.from_dict(valid_keys.get("track", {}))
        if "options" in valid_keys:
            valid_keys["options"] = Options.from_dict(valid_keys.get("options", {}))
        if "restrictions" in valid_keys:
            valid_keys["restrictions"] = Restrictions.from_dict(
                valid_keys.get("restrictions", {})
            )
        if "prev_tracks" in valid_keys:
            valid_keys["prev_tracks"] = [
                Track.from_dict(track) for track in valid_keys.get("prev_tracks", [])
            ]
        if "next_tracks" in valid_keys:
            valid_keys["next_tracks"] = [
                Track.from_dict(track) for track in valid_keys.get("next_tracks", [])
            ]
        if "context_metadata" in valid_keys:
            valid_keys["context_metadata"] = ContextMetadata.from_dict(
                valid_keys.get("context_metadata", {})
            )
        if "playback_quality" in valid_keys:
            valid_keys["playback_quality"] = PlaybackQuality.from_dict(
                valid_keys.get("playback_quality", {})
            )
        return cls(**valid_keys)

    def __str__(self) -> str:
        return "PlayerState()"


# Devices


@dataclass
class Hifi:
    device_supported: bool | None = None

    @staticmethod
    def from_dict(data: Dict) -> "Hifi":
        valid_keys = {
            key: data[key] for key in Hifi.__annotations__.keys() if key in data
        }
        return Hifi(**valid_keys)

    def __str__(self) -> str:
        return "Hifi()"


@dataclass
class AudioOutputDeviceInfo:
    audio_output_device_type: str
    device_name: str

    @staticmethod
    def from_dict(data: Dict) -> "AudioOutputDeviceInfo":
        valid_keys = {
            key: data[key]
            for key in AudioOutputDeviceInfo.__annotations__.keys()
            if key in data
        }
        return AudioOutputDeviceInfo(**valid_keys)

    def __str__(self) -> str:
        return "AudioOutputDeviceInfo()"


@dataclass
class Capabilities:
    can_be_player: bool
    gaia_eq_connect_id: bool
    supports_logout: bool
    is_observable: bool
    volume_steps: int
    supported_types: List[str]
    command_acks: bool
    is_controllable: bool
    supports_external_episodes: bool
    supports_command_request: bool
    supports_set_options_command: bool
    supports_hifi: Union[Hifi, Dict]
    supported_audio_quality: str
    supports_playback_speed: bool
    supports_rename: bool | None = None
    supports_playlist_v2: bool | None = None
    supports_set_backend_metadata: bool | None = None
    supports_transfer_command: bool | None = None
    supports_gzip_pushes: bool | None = None
    supports_dj: bool | None = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Capabilities":
        # Ensure required fields are present
        required_keys = [
            "can_be_player",
            "gaia_eq_connect_id",
            "supports_logout",
            "is_observable",
            "volume_steps",
            "supported_types",
            "command_acks",
            "is_controllable",
            "supports_external_episodes",
            "supports_command_request",
            "supports_set_options_command",
            "supported_audio_quality",
            "supports_playback_speed",
        ]

        # Filter out invalid keys and handle missing fields
        valid_keys = {key: data.get(key) for key in required_keys}

        # Handle 'supports_hifi' separately
        if "supports_hifi" in data:
            if isinstance(data["supports_hifi"], dict):
                valid_keys["supports_hifi"] = Hifi.from_dict(data["supports_hifi"])
            else:
                valid_keys["supports_hifi"] = data["supports_hifi"]
        else:
            valid_keys["supports_hifi"] = {}

        return Capabilities(**valid_keys)  # type: ignore

    def __str__(self) -> str:
        return "Capabilities()"


@dataclass
class MetadataMap:
    device_address_mask: str
    debug_level: str
    tier1_port: str

    @staticmethod
    def from_dict(data: Dict) -> "MetadataMap":
        valid_keys = {
            key: data[key] for key in MetadataMap.__annotations__.keys() if key in data
        }
        return MetadataMap(**valid_keys)

    def __str__(self) -> str:
        return "MetadataMap()"


@dataclass
class Device:
    can_play: bool
    volume: int
    name: str
    capabilities: Capabilities
    device_software_version: str
    device_type: str
    device_id: str
    client_id: str
    brand: str
    model: str
    public_ip: str
    license: str
    spirc_version: str | None = None
    metadata_map: MetadataMap | None = None
    audio_output_device_info: AudioOutputDeviceInfo | None = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Device":
        valid_keys = {
            key: data.get(key) for key in Device.__annotations__.keys() if key in data
        }

        if "capabilities" in valid_keys:
            valid_keys["capabilities"] = Capabilities.from_dict(
                dict(valid_keys["capabilities"])  # type: ignore
            )

        if "metadata_map" in valid_keys and isinstance(
            valid_keys["metadata_map"], dict
        ):
            valid_keys["metadata_map"] = MetadataMap.from_dict(
                valid_keys["metadata_map"]
            )

        if "audio_output_device_info" in valid_keys and isinstance(
            valid_keys["audio_output_device_info"], dict
        ):
            valid_keys["audio_output_device_info"] = AudioOutputDeviceInfo.from_dict(
                valid_keys["audio_output_device_info"]
            )

        return Device(**valid_keys)  # type: ignore

    def __str__(self) -> str:
        return "Device()"


@dataclass
class Devices:
    active_device_id: str | None
    devices: Dict[str, Device]

    @staticmethod
    def from_dict(data: Dict, active_device_id: str | None) -> "Devices":
        devices = {key: Device.from_dict(value) for key, value in data.items()}
        return Devices(devices=devices, active_device_id=active_device_id)

    def __str__(self) -> str:
        return "Devices()"
