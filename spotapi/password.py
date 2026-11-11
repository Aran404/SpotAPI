"""Password recovery using a caller-provided CAPTCHA token or solver."""

from uuid import uuid4

from .account_session import AccountSession
from .captcha import CaptchaChallenge, CaptchaSolver, captcha_token
from .client import AsyncClient
from .types import HTTPError

_SITE_KEY = "6LfCVLAUAAAAALFwwRnnCJ12DalriUGbj8FW_J39"


class PasswordReset:
    """Borrow an open AsyncClient; request an email, then reset with its link token."""

    __slots__ = (
        "http",
        "solver",
        "flow_id",
    )

    def __init__(
        self,
        client: AsyncClient,
        *,
        solver: CaptchaSolver | None = None,
        locale: str = "en",
    ) -> None:
        """Borrow a client and optional CAPTCHA solver for password recovery."""
        if not locale.replace("-", "").replace("_", "").isalpha():
            raise ValueError("Use a language or locale code")
        self.http = AccountSession(
            client, f"https://accounts.spotify.com/{locale}/password-reset", locale=locale
        )
        self.solver = solver
        self.flow_id = str(uuid4())

    async def request(self, email_or_username: str, *, token: str | None = None) -> None:
        """Send a password-recovery email using a fresh CAPTCHA token."""
        if not email_or_username.strip():
            raise ValueError("An email or username is required")
        challenge = CaptchaChallenge(self.http.page, _SITE_KEY, "password_reset_web/recovery")
        solved = await captcha_token(challenge, token, self.solver)
        await self.http.request(
            "POST",
            "/api/password/recovery",
            body={
                "emailOrUsername": email_or_username,
                "captcha": solved,
                "flowId": self.flow_id,
                "attemptId": str(uuid4()),
            },
        )

    async def verify_token(self, token: str) -> bool:
        """Check a reset token; return false for a token Spotify refuses."""
        if not token:
            raise ValueError("A reset-link token is required")
        try:
            await self.http.request("POST", "/api/password/token-verify", body={"token": token})
        except HTTPError as error:
            if error.status_code in {400, 401, 403}:
                return False
            raise
        return True

    async def reset(
        self, reset_token: str, new_password: str, *, token: str | None = None
    ) -> None:
        """Set a new password using a reset token and fresh CAPTCHA response."""
        if not reset_token or not new_password:
            raise ValueError("A reset-link token and new password are required")
        challenge = CaptchaChallenge(self.http.page, _SITE_KEY, "password_reset_web/reset")
        solved = await captcha_token(challenge, token, self.solver)
        await self.http.request(
            "POST",
            "/api/password/reset",
            body={
                "password": new_password,
                "token": reset_token,
                "captcha": solved,
                "flowId": self.flow_id,
            },
        )
