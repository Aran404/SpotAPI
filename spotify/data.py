from dataclasses import dataclass, field
from typing import Type
from spotify.logger import NoopLogger
from spotify.interfaces import CaptchaProtocol, LoggerProtocol
from spotify.http.request import TLSClient


@dataclass
class Config:
    logger: Type[LoggerProtocol]
    solver: Type[CaptchaProtocol] = field(default=NoopLogger())
    client: TLSClient = field(default=TLSClient("chrome_120", "", auto_retries=3))


@dataclass
class SolverConfig:
    api_key: str
    captcha_service: str
    retries: int = field(default=120)
