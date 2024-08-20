from dataclasses import dataclass, field
from spotapi.types.interfaces import CaptchaProtocol, LoggerProtocol
from spotapi.http.request import TLSClient
from typing import List, Dict, Optional, Any, Union


@dataclass
class Config:
    logger: LoggerProtocol
    solver: CaptchaProtocol | None = field(default=None)
    client: TLSClient = field(default=TLSClient("chrome_120", "", auto_retries=3))


@dataclass
class SolverConfig:
    api_key: str
    captcha_service: str
    retries: int = field(default=120)


@dataclass
class Metadata:
    ORIGINAL_SESSION_ID: Optional[str] = None
    album_title: Optional[str] = None
    image_xlarge_url: Optional[str] = None
    actions_skipping_next_past_track: Optional[str] = None
    interaction_id: Optional[str] = None
    title: Optional[str] = None
    artist_uri: Optional[str] = None
    image_url: Optional[str] = None
    entity_uri: Optional[str] = None
    image_large_url: Optional[str] = None
    iteration: Optional[str] = None
    actions_skipping_prev_past_track: Optional[str] = None
    page_instance_id: Optional[str] = None
    album_uri: Optional[str] = None
    image_small_url: Optional[str] = None
    track_player: Optional[str] = None
    context_uri: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Metadata":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)


@dataclass
class Track:
    uri: Optional[str] = None
    uid: Optional[str] = None
    metadata: Optional[Metadata] = None
    provider: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Track":
        metadata = data.get("metadata", {})
        if isinstance(metadata, dict):
            data["metadata"] = Metadata.from_dict(metadata)
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)


@dataclass
class Index:
    page: Optional[int] = None
    track: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Index":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)


@dataclass
class PlayOrigin:
    feature_identifier: Optional[str] = None
    feature_version: Optional[str] = None
    referrer_identifier: Optional[str] = None
    device_identifier: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlayOrigin":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)


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


@dataclass
class Options:
    shuffling_context: Optional[bool] = None
    repeating_context: Optional[bool] = None
    repeating_track: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Options":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)


@dataclass
class PlaybackQuality:
    bitrate_level: Optional[str] = None
    strategy: Optional[str] = None
    target_bitrate_level: Optional[str] = None
    target_bitrate_available: Optional[bool] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PlaybackQuality":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)


@dataclass
class ContextMetadata:
    image_url: Optional[str] = None
    context_description: Optional[str] = None
    context_owner: Optional[str] = None
    playlist_number_of_tracks: Optional[str] = None
    playlist_number_of_episodes: Optional[str] = None
    player_arch: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContextMetadata":
        valid_keys = {
            key: data[key] for key in cls.__annotations__.keys() if key in data
        }
        return cls(**valid_keys)


@dataclass
class PlayerState:
    timestamp: Optional[str] = None
    context_uri: Optional[str] = None
    context_url: Optional[str] = None
    context_restrictions: Dict[str, str] = field(default_factory=dict)
    play_origin: Optional[PlayOrigin] = None
    index: Optional[Index] = None
    track: Optional[Track] = None
    playback_id: Optional[str] = None
    playback_speed: Optional[float] = None
    position_as_of_timestamp: Optional[str] = None
    duration: Optional[str] = None
    is_playing: Optional[bool] = None
    is_paused: Optional[bool] = None
    is_system_initiated: Optional[bool] = None
    options: Optional[Options] = None
    restrictions: Optional[Restrictions] = None
    suppressions: Dict[str, str] = field(default_factory=dict)
    prev_tracks: List[Track] = field(default_factory=list)
    next_tracks: List[Track] = field(default_factory=list)
    context_metadata: Optional[ContextMetadata] = None
    page_metadata: Dict[str, str] = field(default_factory=dict)
    session_id: Optional[str] = None
    queue_revision: Optional[str] = None
    playback_quality: Optional[PlaybackQuality] = None

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


# Devices


@dataclass
class Hifi:
    device_supported: Optional[bool] = None

    @staticmethod
    def from_dict(data: Dict) -> "Hifi":
        valid_keys = {
            key: data[key] for key in Hifi.__annotations__.keys() if key in data
        }
        return Hifi(**valid_keys)


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
    supports_rename: Optional[bool] = None
    supports_playlist_v2: Optional[bool] = None
    supports_set_backend_metadata: Optional[bool] = None
    supports_transfer_command: Optional[bool] = None
    supports_gzip_pushes: Optional[bool] = None
    supports_dj: Optional[bool] = None

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
    spirc_version: Optional[str] = None
    metadata_map: Optional[MetadataMap] = None
    audio_output_device_info: Optional[AudioOutputDeviceInfo] = None

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


@dataclass
class Devices:
    active_device_id: Optional[str]
    devices: Dict[str, Device]

    @staticmethod
    def from_dict(data: Dict, active_device_id: Optional[str]) -> "Devices":
        devices = {key: Device.from_dict(value) for key, value in data.items()}
        return Devices(devices=devices, active_device_id=active_device_id)
