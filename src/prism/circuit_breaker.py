"""Circuit breaker for external API calls.

Prevents cascading failures by short-circuiting calls to unhealthy services.
Each service gets its own independent breaker instance.
"""

import logging
import threading
import time
from enum import StrEnum

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when a call is attempted on an open circuit."""

    def __init__(self, name: str, retry_after: float) -> None:
        self.name = name
        self.retry_after = retry_after
        super().__init__(
            f"Circuit '{name}' is open. Retry after {retry_after:.0f}s."
        )


class CircuitBreaker:
    """Simple circuit breaker with three states.

    CLOSED  — normal operation, failures are counted.
    OPEN    — calls rejected immediately with CircuitOpenError.
    HALF_OPEN — one test call allowed; success resets, failure reopens.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 300.0,
    ) -> None:
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._lock = threading.Lock()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.monotonic() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    logger.info("Circuit '%s' moved to HALF_OPEN", self.name)
            return self._state

    def record_success(self) -> None:
        """Record a successful call — reset to CLOSED."""
        with self._lock:
            if self._state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
                self._failure_count = 0
                self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        """Record a failed call — increment counter, possibly open."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' reopened after half-open failure", self.name,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit '%s' opened after %d consecutive failures",
                    self.name, self._failure_count,
                )

    def __call__(self, fn):
        """Use as a decorator wrapping an external call."""
        import functools

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            state = self.state
            if state == CircuitState.OPEN:
                retry_after = self.recovery_timeout - (
                    time.monotonic() - self._last_failure_time
                )
                raise CircuitOpenError(self.name, max(0.0, retry_after))
            try:
                result = fn(*args, **kwargs)
                self.record_success()
                return result
            except Exception:
                self.record_failure()
                raise

        return wrapper

    def reset(self) -> None:
        """Reset breaker to initial CLOSED state (for testing)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0


# ── Per-service breaker instances ────────────────────────────────────

brave_breaker = CircuitBreaker("brave_api", failure_threshold=5, recovery_timeout=300.0)
claude_breaker = CircuitBreaker("claude_api", failure_threshold=5, recovery_timeout=300.0)
openai_tts_breaker = CircuitBreaker("openai_tts", failure_threshold=5, recovery_timeout=300.0)
