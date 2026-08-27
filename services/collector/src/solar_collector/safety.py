from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field

logger = __import__("logging").getLogger(__name__)


class CircuitOpenError(RuntimeError):
    """Raised when the PVS circuit breaker is open."""


@dataclass
class CircuitBreaker:
    failure_threshold: int = 3
    reset_seconds: float = 900.0
    failures: int = 0
    opened_at: float | None = None

    def before_call(self) -> None:
        if self.opened_at is None:
            return
        elapsed = time.monotonic() - self.opened_at
        if elapsed >= self.reset_seconds:
            logger.info("circuit_breaker_half_open_reset")
            self.failures = 0
            self.opened_at = None
            return
        raise CircuitOpenError(
            f"circuit open for {self.reset_seconds - elapsed:.0f}s more "
            f"after {self.failure_threshold} failures"
        )

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()
            logger.error(
                "circuit_breaker_opened failures=%s reset_s=%s",
                self.failures,
                self.reset_seconds,
            )


@dataclass
class RequestGate:
    """Enforces single-flight requests and optional minimum spacing."""

    max_concurrency: int = 1
    min_interval_seconds: float = 0.0
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _last_request_at: float | None = None

    async def __aenter__(self) -> None:
        if self.max_concurrency != 1:
            raise ValueError("only concurrency=1 is supported for PVS safety")
        await self._lock.acquire()
        if self._last_request_at is not None and self.min_interval_seconds > 0:
            wait = self.min_interval_seconds - (time.monotonic() - self._last_request_at)
            if wait > 0:
                await asyncio.sleep(wait)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._last_request_at = time.monotonic()
        self._lock.release()
