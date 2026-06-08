"""Sliding-window in-memory rate limiter middleware for FastAPI."""

import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding-window rate limiter.

    Args:
        app: The ASGI application.
        public_rpm: Requests per minute for unauthenticated requests.
        authenticated_rpm: Requests per minute for authenticated requests.
        window_seconds: Sliding window size in seconds.
    """

    def __init__(
        self,
        app,  # type: ignore[no-untyped-def]
        public_rpm: int = 60,
        authenticated_rpm: int = 120,
        window_seconds: int = 60,
    ) -> None:
        super().__init__(app)
        self.public_rpm = public_rpm
        self.authenticated_rpm = authenticated_rpm
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP from request."""
        if request.client:
            return request.client.host
        return "unknown"

    def _clean_window(self, timestamps: deque[float], now: float) -> None:
        """Remove timestamps outside the sliding window."""
        cutoff = now - self.window_seconds
        while timestamps and timestamps[0] < cutoff:
            timestamps.popleft()

    # Paths excluded from rate limiting (e.g. Stripe sends legitimate bursts)
    _EXEMPT_PATHS = frozenset({"/webhooks/stripe"})

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path in self._EXEMPT_PATHS:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.monotonic()

        if client_ip not in self._hits:
            self._hits[client_ip] = deque()

        timestamps = self._hits[client_ip]
        self._clean_window(timestamps, now)

        has_api_key = bool(request.headers.get("X-API-Key"))
        limit = self.authenticated_rpm if has_api_key else self.public_rpm

        if len(timestamps) >= limit:
            retry_after = int(self.window_seconds - (now - timestamps[0])) + 1
            return JSONResponse(
                status_code=429,
                content={"detail": "Too many requests"},
                headers={"Retry-After": str(retry_after)},
            )

        timestamps.append(now)
        return await call_next(request)
