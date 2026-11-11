"""Backward-compatible imports for the HTTP transport.

The implementation lives in :mod:`spotapi.connection.http`.
"""

from .http import HTTPClient, RateLimiter

__all__ = ("HTTPClient", "RateLimiter")
