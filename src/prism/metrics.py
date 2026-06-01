"""Simple in-process metrics collection for observability.

Provides Counter, Gauge, and Histogram metric types stored in a
module-level registry.  The ``GET /metrics`` API endpoint returns a
JSON snapshot of all registered metrics.
"""

from __future__ import annotations

import functools
import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable


_lock = threading.RLock()
_registry: dict[str, "Counter | Gauge | Histogram"] = {}


def _register(name: str, metric: "Counter | Gauge | Histogram") -> None:
    with _lock:
        if name in _registry:
            raise ValueError(f"Metric '{name}' already registered")
        _registry[name] = metric


def get_metric(name: str) -> "Counter | Gauge | Histogram | None":
    """Retrieve a registered metric by name."""
    return _registry.get(name)


def snapshot() -> dict[str, dict]:
    """Return a JSON-serialisable snapshot of all registered metrics."""
    with _lock:
        return {name: m.snapshot() for name, m in sorted(_registry.items())}


def reset_all() -> None:
    """Clear all registered metrics (for testing only)."""
    with _lock:
        _registry.clear()


def _restore_defaults() -> None:
    """Re-register module-level application metrics after reset_all().

    Needed so that tests calling reset_all() don't orphan the global
    metric objects for subsequent test modules.
    """
    for name, obj in globals().items():
        if isinstance(obj, (Counter, Gauge, Histogram)) and obj.name not in _registry:
            _registry[obj.name] = obj


# ── Metric types ─────────────────────────────────────────────────────


@dataclass
class Counter:
    """Monotonically increasing counter."""

    name: str
    _value: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        _register(self.name, self)

    def inc(self, amount: float = 1.0) -> None:
        if amount < 0:
            raise ValueError("Counter increment must be non-negative")
        with _lock:
            self._value += amount

    @property
    def value(self) -> float:
        return self._value

    def snapshot(self) -> dict:
        return {"type": "counter", "value": self._value}


@dataclass
class Gauge:
    """Value that can go up and down."""

    name: str
    _value: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        _register(self.name, self)

    def set(self, value: float) -> None:
        with _lock:
            self._value = value

    def inc(self, amount: float = 1.0) -> None:
        with _lock:
            self._value += amount

    def dec(self, amount: float = 1.0) -> None:
        with _lock:
            self._value -= amount

    @property
    def value(self) -> float:
        return self._value

    def snapshot(self) -> dict:
        return {"type": "gauge", "value": self._value}


@dataclass
class Histogram:
    """Records observed values and computes summary statistics."""

    name: str
    _values: list[float] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        _register(self.name, self)

    def observe(self, value: float) -> None:
        with _lock:
            self._values.append(value)

    @property
    def count(self) -> int:
        return len(self._values)

    def snapshot(self) -> dict:
        with _lock:
            if not self._values:
                return {"type": "histogram", "count": 0, "sum": 0.0,
                        "min": 0.0, "max": 0.0, "avg": 0.0}
            _sum = 0.0
            for v in self._values:
                _sum += v
            return {
                "type": "histogram",
                "count": len(self._values),
                "sum": _sum,
                "min": min(self._values),
                "max": max(self._values),
                "avg": _sum / len(self._values),
            }


# ── Default application metrics ─────────────────────────────────────
# Imported by agents / middleware at runtime.

discovery_articles_total = Counter("discovery_articles_total")
discovery_clusters_stored = Counter("discovery_clusters_stored")
discovery_brave_skip_total = Counter("discovery_brave_skip_total")
analysis_duration_seconds = Histogram("analysis_duration_seconds")
resonance_computed_total = Counter("resonance_computed_total")
perception_computed_total = Counter("perception_computed_total")
briefing_sent_total = Counter("briefing_sent_total")
api_requests_total = Counter("api_requests_total")
cycle_successes_total = Counter("cycle_successes_total")
cycle_failures_total = Counter("cycle_failures_total")
cycle_duration_seconds = Histogram("cycle_duration_seconds")

_timed_logger = logging.getLogger("prism.metrics")


# ── timed_cycle decorator ────────────────────────────────────────────


def timed_cycle(name: str) -> Callable:
    """Decorator that logs cycle timing/status and updates metrics.

    Args:
        name: Human-readable cycle name (e.g. "discovery", "analysis").
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                elapsed = time.monotonic() - start
                cycle_successes_total.inc()
                cycle_duration_seconds.observe(elapsed)
                _timed_logger.info(
                    "Cycle '%s' completed in %.3fs", name, elapsed,
                )
                return result
            except Exception:
                elapsed = time.monotonic() - start
                cycle_failures_total.inc()
                cycle_duration_seconds.observe(elapsed)
                _timed_logger.error(
                    "Cycle '%s' failed after %.3fs", name, elapsed,
                    exc_info=True,
                )
                raise

        return wrapper

    return decorator
