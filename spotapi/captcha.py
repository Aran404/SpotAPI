"""Provider-neutral CAPTCHA requests for account operations."""

from dataclasses import dataclass
from typing import Literal, Protocol

from .types import SpotAPIError


@dataclass(frozen=True, slots=True)
class CaptchaChallenge:
    website_url: str
    site_key: str
    action: str
    version: Literal["v2", "v3"] = "v3"
    enterprise: bool = True


class CaptchaSolver(Protocol):
    async def solve(self, challenge: CaptchaChallenge) -> str:
        """Return a fresh token for the supplied website, key and action."""
        ...


class CaptchaRequired(SpotAPIError):
    def __init__(self, challenge: CaptchaChallenge) -> None:
        """Retain the required CAPTCHA challenge without selecting a solver vendor."""
        super().__init__("Provide a CAPTCHA token or an async CaptchaSolver")
        self.challenge = challenge


async def captcha_token(
    challenge: CaptchaChallenge, token: str | None, solver: CaptchaSolver | None
) -> str:
    """Use an explicit token or async solver; raise CaptchaRequired when neither exists."""
    if token is None:
        if solver is None:
            raise CaptchaRequired(challenge)
        token = await solver.solve(challenge)

    if not token.strip():
        raise ValueError("The CAPTCHA token must not be empty")
    return token
