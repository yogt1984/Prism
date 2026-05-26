"""Shared test configuration.

Sets minimal env vars so that Settings() doesn't fail during test collection.
"""

import os

import pytest

# Provide dummy values for required config fields during testing.
# These are never used — agents are not called in unit tests.
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-ant-test-dummy")


@pytest.fixture(autouse=True)
def _reset_circuit_breakers():
    """Reset circuit breakers between every test to prevent state leakage."""
    from prism.circuit_breaker import brave_breaker, claude_breaker

    brave_breaker.reset()
    claude_breaker.reset()
    yield
    brave_breaker.reset()
    claude_breaker.reset()
