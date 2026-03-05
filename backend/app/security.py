"""Security dependencies and middleware for Sentinel API."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import APIKeyHeader
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.settings import Settings, get_settings

API_KEY_HEADER_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_HEADER_NAME, auto_error=False)


def require_api_key(
    request_api_key: str | None = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> None:
    """
    Enforce API key auth when SENTINEL_API_KEYS is configured.
    If no keys are configured, auth is bypassed for local demo operation.
    """
    valid_keys = settings.parsed_api_keys
    if not valid_keys:
        return
    if request_api_key is None or request_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline hardening headers to every response."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized requests using Content-Length guardrails."""

    def __init__(self, app, max_body_bytes: int):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                size = int(content_length)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
            if size > self.max_body_bytes:
                return JSONResponse(
                    status_code=413,
                    content={"detail": f"Payload too large. Max {self.max_body_bytes} bytes."},
                )
        return await call_next(request)


@dataclass
class RateLimitDecision:
    allowed: bool
    remaining: int
    retry_after_seconds: int


class InMemoryRateLimiter:
    """
    Simple in-memory per-client limiter.
    Suitable for prototype/demo use; replace with Redis in multi-instance deployments.
    """

    def __init__(self, limit_per_minute: int):
        self.limit_per_minute = limit_per_minute
        self._state: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()

    def check(self, client_id: str) -> RateLimitDecision:
        now = time.monotonic()
        with self._lock:
            window_started, count = self._state.get(client_id, (now, 0))
            elapsed = now - window_started

            if elapsed >= 60.0:
                window_started, count = now, 0
                elapsed = 0.0

            if count >= self.limit_per_minute:
                retry_after = max(1, int(60 - elapsed))
                return RateLimitDecision(
                    allowed=False,
                    remaining=0,
                    retry_after_seconds=retry_after,
                )

            count += 1
            self._state[client_id] = (window_started, count)
            remaining = max(0, self.limit_per_minute - count)
            retry_after = max(1, int(60 - elapsed))
            return RateLimitDecision(
                allowed=True,
                remaining=remaining,
                retry_after_seconds=retry_after,
            )


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, limiter: InMemoryRateLimiter):
        super().__init__(app)
        self.limiter = limiter

    @staticmethod
    def _client_id(request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        if request.client and request.client.host:
            return request.client.host
        return "unknown"

    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/health":
            return await call_next(request)

        decision = self.limiter.check(self._client_id(request))
        if not decision.allowed:
            response = JSONResponse(status_code=429, content={"detail": "Rate limit exceeded"})
            response.headers["Retry-After"] = str(decision.retry_after_seconds)
            response.headers["X-RateLimit-Limit"] = str(self.limiter.limit_per_minute)
            response.headers["X-RateLimit-Remaining"] = "0"
            return response

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limiter.limit_per_minute)
        response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
        return response
