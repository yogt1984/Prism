"""T15.2: Per-cycle timing and status logging tests."""

import logging
import time

import pytest

from prism.metrics import (
    Counter,
    Histogram,
    cycle_duration_seconds,
    cycle_failures_total,
    cycle_successes_total,
    reset_all,
    snapshot,
    timed_cycle,
)


@pytest.fixture(autouse=True)
def _fresh_metrics():
    """Reload metrics module to get fresh counters for each test."""
    from importlib import reload
    import prism.metrics
    reset_all()
    reload(prism.metrics)
    # Re-bind module-level references after reload
    global cycle_successes_total, cycle_failures_total, cycle_duration_seconds
    cycle_successes_total = prism.metrics.cycle_successes_total
    cycle_failures_total = prism.metrics.cycle_failures_total
    cycle_duration_seconds = prism.metrics.cycle_duration_seconds
    yield


# ══════════════════════════════════════════════════════════════════════
# Decorator behavior
# ══════════════════════════════════════════════════════════════════════


class TestTimedCycleDecorator:

    def test_success_increments_counter(self):
        @timed_cycle("test_ok")
        def do_work():
            return 42

        do_work()
        assert cycle_successes_total.value == 1.0

    def test_failure_increments_counter(self):
        @timed_cycle("test_fail")
        def do_fail():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            do_fail()
        assert cycle_failures_total.value == 1.0

    def test_success_does_not_increment_failure(self):
        @timed_cycle("ok_only")
        def do_ok():
            pass

        do_ok()
        assert cycle_failures_total.value == 0.0

    def test_failure_does_not_increment_success(self):
        @timed_cycle("fail_only")
        def do_fail():
            raise ValueError("bad")

        with pytest.raises(ValueError):
            do_fail()
        assert cycle_successes_total.value == 0.0

    def test_preserves_return_value(self):
        @timed_cycle("retval")
        def compute():
            return {"answer": 42}

        result = compute()
        assert result == {"answer": 42}

    def test_preserves_none_return(self):
        @timed_cycle("none_ret")
        def do_nothing():
            pass

        assert do_nothing() is None

    def test_reraises_exception(self):
        @timed_cycle("reraise")
        def explode():
            raise TypeError("wrong type")

        with pytest.raises(TypeError, match="wrong type"):
            explode()

    def test_preserves_function_name(self):
        @timed_cycle("named")
        def my_function():
            pass

        assert my_function.__name__ == "my_function"

    def test_preserves_docstring(self):
        @timed_cycle("docs")
        def documented():
            """This is documented."""
            pass

        assert documented.__doc__ == "This is documented."

    def test_multiple_calls_accumulate(self):
        @timed_cycle("multi")
        def tick():
            pass

        tick()
        tick()
        tick()
        assert cycle_successes_total.value == 3.0

    def test_mixed_success_and_failure(self):
        @timed_cycle("mixed")
        def maybe_fail(fail: bool):
            if fail:
                raise RuntimeError("fail")

        maybe_fail(False)
        maybe_fail(False)
        with pytest.raises(RuntimeError):
            maybe_fail(True)

        assert cycle_successes_total.value == 2.0
        assert cycle_failures_total.value == 1.0


# ══════════════════════════════════════════════════════════════════════
# Timing accuracy
# ══════════════════════════════════════════════════════════════════════


class TestTimedCycleTiming:

    def test_duration_recorded_on_success(self):
        @timed_cycle("timed_ok")
        def slow():
            time.sleep(0.05)

        slow()
        snap = cycle_duration_seconds.snapshot()
        assert snap["count"] == 1
        assert snap["min"] >= 0.04  # allow small timing jitter

    def test_duration_recorded_on_failure(self):
        @timed_cycle("timed_fail")
        def slow_fail():
            time.sleep(0.05)
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            slow_fail()
        snap = cycle_duration_seconds.snapshot()
        assert snap["count"] == 1
        assert snap["min"] >= 0.04

    def test_timer_accuracy(self):
        """Measured duration should be within 50ms of actual sleep time."""
        @timed_cycle("accuracy")
        def sleep_100ms():
            time.sleep(0.1)

        sleep_100ms()
        snap = cycle_duration_seconds.snapshot()
        measured = snap["min"]
        assert abs(measured - 0.1) < 0.05


# ══════════════════════════════════════════════════════════════════════
# Logging output
# ══════════════════════════════════════════════════════════════════════


class TestTimedCycleLogging:

    def test_success_logs_info(self, caplog):
        @timed_cycle("log_ok")
        def work():
            pass

        with caplog.at_level(logging.INFO, logger="prism.metrics"):
            work()

        assert any("log_ok" in r.message and "completed" in r.message
                    for r in caplog.records)

    def test_success_logs_duration(self, caplog):
        @timed_cycle("log_dur")
        def work():
            pass

        with caplog.at_level(logging.INFO, logger="prism.metrics"):
            work()

        # Should contain a float like "0.001s"
        assert any("log_dur" in r.message and "s" in r.message
                    for r in caplog.records)

    def test_failure_logs_error(self, caplog):
        @timed_cycle("log_fail")
        def fail():
            raise RuntimeError("test error")

        with caplog.at_level(logging.ERROR, logger="prism.metrics"):
            with pytest.raises(RuntimeError):
                fail()

        assert any("log_fail" in r.message and "failed" in r.message
                    for r in caplog.records)

    def test_failure_log_level_is_error(self, caplog):
        @timed_cycle("log_level")
        def fail():
            raise RuntimeError("err")

        with caplog.at_level(logging.DEBUG, logger="prism.metrics"):
            with pytest.raises(RuntimeError):
                fail()

        error_records = [r for r in caplog.records
                         if r.levelno == logging.ERROR and "log_level" in r.message]
        assert len(error_records) >= 1


# ══════════════════════════════════════════════════════════════════════
# Metrics endpoint integration
# ══════════════════════════════════════════════════════════════════════


class TestTimedCycleInSnapshot:

    def test_cycle_metrics_in_snapshot(self):
        snap = snapshot()
        assert "cycle_successes_total" in snap
        assert "cycle_failures_total" in snap
        assert "cycle_duration_seconds" in snap

    def test_snapshot_updates_after_cycle(self):
        @timed_cycle("snap_test")
        def work():
            pass

        work()
        snap = snapshot()
        assert snap["cycle_successes_total"]["value"] == 1.0
        assert snap["cycle_duration_seconds"]["count"] == 1


# ══════════════════════════════════════════════════════════════════════
# Agent method decoration verification
# ══════════════════════════════════════════════════════════════════════


class TestAgentDecoration:
    """Verify the decorator is applied to actual agent methods."""

    def test_discovery_agent_decorated(self):
        from prism.agents.d_ai import DiscoveryAgent
        assert DiscoveryAgent.run_discovery.__wrapped__  # functools.wraps sets this

    def test_analysis_agent_decorated(self):
        from prism.agents.a_ai import AnalysisAgent
        assert AnalysisAgent.process_pending.__wrapped__

    def test_writer_agent_decorated(self):
        from prism.agents.w_ai import WriterAgent
        assert WriterAgent.create_and_send.__wrapped__
