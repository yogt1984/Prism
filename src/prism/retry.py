"""Retry decorator with exponential backoff for transient failures."""

import logging
import time
from collections.abc import Callable
from functools import wraps
from typing import Any

import anthropic
import httpx

logger = logging.getLogger(__name__)

# Exceptions considered transient and worth retrying
TRANSIENT_EXCEPTIONS: tuple[type[Exception], ...] = (
    httpx.TimeoutException,
    httpx.ConnectError,
    ConnectionError,
    TimeoutError,
    anthropic.RateLimitError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)


def _is_transient_http_error(exc: httpx.HTTPStatusError) -> bool:
    """429 (rate limit) and 5xx (server errors) are transient."""
    return exc.response.status_code == 429 or exc.response.status_code >= 500


def retry_on_transient(
    max_retries: int = 3,
    base_delay: float = 1.0,
    extra_exceptions: tuple[type[Exception], ...] = (),
) -> Callable:
    """Decorator: retry on transient network/API errors with exponential backoff.

    Args:
        extra_exceptions: Additional exception types to retry on (e.g. for
            third-party SDKs that raise generic Exception on server errors).
    """

    def decorator(fn: Callable) -> Callable:
        all_transient = TRANSIENT_EXCEPTIONS + extra_exceptions

        @wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_retries + 1):
                try:
                    return fn(*args, **kwargs)
                except httpx.HTTPStatusError as exc:
                    if not _is_transient_http_error(exc):
                        raise
                    last_exc = exc
                except all_transient as exc:
                    last_exc = exc
                except Exception:
                    raise

                if attempt < max_retries:
                    delay = base_delay * (2 ** (attempt - 1))
                    logger.warning(
                        "Retry %d/%d for %s after %.1fs (error: %s)",
                        attempt, max_retries,
                        getattr(fn, "__name__", str(fn)), delay, last_exc,
                    )
                    time.sleep(delay)

            raise last_exc  # type: ignore[misc]

        return wrapper
    return decorator
