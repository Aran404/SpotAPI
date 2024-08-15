from dataclasses import dataclass, field
from spotapi.types.interfaces import CaptchaProtocol, LoggerProtocol
from spotapi.http.request import TLSClient


@dataclass
class Config:
    solver: CaptchaProtocol
    logger: LoggerProtocol
    client: TLSClient = field(default=TLSClient("chrome_120", "", auto_retries=3))


@dataclass
class SolverConfig:
    api_key: str
    captcha_service: str
    retries: int = field(default=120)
