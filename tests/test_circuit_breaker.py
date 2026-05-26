"""T18.1: Circuit breaker tests."""

import time
from unittest.mock import patch

import pytest

from prism.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
    brave_breaker,
    claude_breaker,
)


@pytest.fixture(autouse=True)
def _reset_breakers():
    """Reset module-level breakers between tests."""
    brave_breaker.reset()
    claude_breaker.reset()
    yield
    brave_breaker.reset()
    claude_breaker.reset()


# ══════════════════════════════════════════════════════════════════════
# Core CircuitBreaker logic
# ══════════════════════════════════════════════════════════════════════


class TestCircuitBreakerStates:

    def test_initial_state_closed(self):
        cb = CircuitBreaker("test")
        assert cb.state == CircuitState.CLOSED

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_opens_at_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(5):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_opens_above_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3)
        for _ in range(10):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=5)
        for _ in range(4):
            cb.record_failure()
        cb.record_success()
        # Should be back to 0 failures
        for _ in range(4):
            cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

    def test_half_open_success_closes(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED


# ══════════════════════════════════════════════════════════════════════
# Decorator usage
# ══════════════════════════════════════════════════════════════════════


class TestCircuitBreakerDecorator:

    def test_decorator_passes_through_on_closed(self):
        cb = CircuitBreaker("test", failure_threshold=5)

        @cb
        def fn():
            return 42

        assert fn() == 42

    def test_decorator_records_success(self):
        cb = CircuitBreaker("test", failure_threshold=5)

        @cb
        def fn():
            return "ok"

        fn()
        assert cb._failure_count == 0

    def test_decorator_records_failure(self):
        cb = CircuitBreaker("test", failure_threshold=5)

        @cb
        def fn():
            raise ConnectionError("down")

        with pytest.raises(ConnectionError):
            fn()
        assert cb._failure_count == 1

    def test_decorator_raises_circuit_open_error(self):
        cb = CircuitBreaker("test", failure_threshold=2)

        @cb
        def fn():
            raise ConnectionError("down")

        # Trip the breaker
        for _ in range(2):
            with pytest.raises(ConnectionError):
                fn()

        # Now should raise CircuitOpenError
        with pytest.raises(CircuitOpenError) as exc_info:
            fn()
        assert "test" in str(exc_info.value)
        assert exc_info.value.retry_after >= 0

    def test_decorator_allows_call_in_half_open(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        call_count = 0

        @cb
        def fn():
            nonlocal call_count
            call_count += 1
            return "ok"

        # Trip with manual failures
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        result = fn()
        assert result == "ok"
        assert call_count == 1
        assert cb.state == CircuitState.CLOSED

    def test_decorator_preserves_function_name(self):
        cb = CircuitBreaker("test")

        @cb
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_decorator_passes_args(self):
        cb = CircuitBreaker("test")

        @cb
        def add(a, b):
            return a + b

        assert add(3, 4) == 7

    def test_decorator_passes_kwargs(self):
        cb = CircuitBreaker("test")

        @cb
        def greet(name="world"):
            return f"hello {name}"

        assert greet(name="test") == "hello test"


# ══════════════════════════════════════════════════════════════════════
# Independent breakers
# ══════════════════════════════════════════════════════════════════════


class TestIndependentBreakers:

    def test_brave_and_claude_are_independent(self):
        """Tripping one breaker doesn't affect the other."""
        for _ in range(5):
            brave_breaker.record_failure()
        assert brave_breaker.state == CircuitState.OPEN
        assert claude_breaker.state == CircuitState.CLOSED

    def test_claude_open_brave_still_works(self):
        for _ in range(5):
            claude_breaker.record_failure()
        assert claude_breaker.state == CircuitState.OPEN
        assert brave_breaker.state == CircuitState.CLOSED

    def test_both_can_be_open(self):
        for _ in range(5):
            brave_breaker.record_failure()
            claude_breaker.record_failure()
        assert brave_breaker.state == CircuitState.OPEN
        assert claude_breaker.state == CircuitState.OPEN

    def test_resetting_one_doesnt_affect_other(self):
        for _ in range(5):
            brave_breaker.record_failure()
            claude_breaker.record_failure()
        brave_breaker.reset()
        assert brave_breaker.state == CircuitState.CLOSED
        assert claude_breaker.state == CircuitState.OPEN


# ══════════════════════════════════════════════════════════════════════
# CircuitOpenError
# ══════════════════════════════════════════════════════════════════════


class TestCircuitOpenError:

    def test_error_attributes(self):
        err = CircuitOpenError("brave_api", 120.5)
        assert err.name == "brave_api"
        assert err.retry_after == 120.5
        assert "brave_api" in str(err)
        assert "120" in str(err)

    def test_is_exception(self):
        assert issubclass(CircuitOpenError, Exception)


# ══════════════════════════════════════════════════════════════════════
# Integration: breakers applied to agents
# ══════════════════════════════════════════════════════════════════════


class TestAgentIntegration:

    def test_brave_breaker_on_search_brave(self):
        """search_brave is wrapped by brave_breaker."""
        from prism.agents.d_ai import DiscoveryAgent

        # Trip the breaker
        for _ in range(5):
            brave_breaker.record_failure()

        agent = DiscoveryAgent()
        with pytest.raises(CircuitOpenError) as exc_info:
            agent.search_brave("test query")
        assert exc_info.value.name == "brave_api"

    def test_claude_breaker_on_a_ai(self):
        """a_ai._call_claude is wrapped by claude_breaker."""
        from prism.agents.a_ai import AnalysisAgent

        for _ in range(5):
            claude_breaker.record_failure()

        agent = AnalysisAgent()
        with pytest.raises(CircuitOpenError) as exc_info:
            agent._call_claude("test prompt")
        assert exc_info.value.name == "claude_api"

    def test_claude_breaker_on_w_ai(self):
        """w_ai._call_claude is wrapped by claude_breaker."""
        from prism.agents.w_ai import WriterAgent

        for _ in range(5):
            claude_breaker.record_failure()

        agent = WriterAgent()
        with pytest.raises(CircuitOpenError) as exc_info:
            agent._call_claude("test prompt")
        assert exc_info.value.name == "claude_api"

    def test_brave_open_doesnt_block_claude(self):
        """Brave circuit open should not prevent Claude calls."""
        from prism.agents.a_ai import AnalysisAgent

        for _ in range(5):
            brave_breaker.record_failure()

        # Claude breaker is still closed — should not raise CircuitOpenError
        # (will fail for other reasons since no real API, but not CircuitOpenError)
        agent = AnalysisAgent()
        assert claude_breaker.state == CircuitState.CLOSED
