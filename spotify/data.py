from dataclasses import dataclass, field
from typing import Type
from spotify.interfaces import CaptchaProtocol, LoggerProtocol
from spotify.http.request import TLSClient


@dataclass
class Config:
    logger: Type[LoggerProtocol]
    solver: Type[CaptchaProtocol]
    client: TLSClient = field(default=TLSClient("chrome_120", "", auto_retries=3))


@dataclass
class SolverConfig:
    api_key: str
    captcha_service: str
    retries: int = field(default=120)
