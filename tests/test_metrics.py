"""T15.1: Structured metrics collection tests."""

import pytest
from fastapi.testclient import TestClient

from prism import metrics
from prism.metrics import Counter, Gauge, Histogram, get_metric, reset_all, snapshot


@pytest.fixture(autouse=True)
def _clean_registry():
    """Ensure a fresh metric registry for each test."""
    reset_all()
    yield
    reset_all()


# ══════════════════════════════════════════════════════════════════════
# Counter
# ══════════════════════════════════════════════════════════════════════


class TestCounter:

    def test_counter_starts_at_zero(self):
        c = Counter("test_c")
        assert c.value == 0.0

    def test_counter_inc_default(self):
        c = Counter("test_c")
        c.inc()
        assert c.value == 1.0

    def test_counter_inc_custom_amount(self):
        c = Counter("test_c")
        c.inc(5)
        assert c.value == 5.0

    def test_counter_inc_multiple(self):
        c = Counter("test_c")
        c.inc()
        c.inc()
        c.inc(3)
        assert c.value == 5.0

    def test_counter_rejects_negative(self):
        c = Counter("test_c")
        with pytest.raises(ValueError, match="non-negative"):
            c.inc(-1)

    def test_counter_snapshot(self):
        c = Counter("test_c")
        c.inc(7)
        snap = c.snapshot()
        assert snap == {"type": "counter", "value": 7.0}

    def test_counter_registered(self):
        c = Counter("test_c")
        assert get_metric("test_c") is c

    def test_duplicate_name_raises(self):
        Counter("dup")
        with pytest.raises(ValueError, match="already registered"):
            Counter("dup")


# ══════════════════════════════════════════════════════════════════════
# Gauge
# ══════════════════════════════════════════════════════════════════════


class TestGauge:

    def test_gauge_starts_at_zero(self):
        g = Gauge("test_g")
        assert g.value == 0.0

    def test_gauge_set(self):
        g = Gauge("test_g")
        g.set(42.5)
        assert g.value == 42.5

    def test_gauge_inc(self):
        g = Gauge("test_g")
        g.inc()
        assert g.value == 1.0

    def test_gauge_dec(self):
        g = Gauge("test_g")
        g.set(10)
        g.dec(3)
        assert g.value == 7.0

    def test_gauge_can_go_negative(self):
        g = Gauge("test_g")
        g.dec(5)
        assert g.value == -5.0

    def test_gauge_snapshot(self):
        g = Gauge("test_g")
        g.set(99)
        assert g.snapshot() == {"type": "gauge", "value": 99.0}

    def test_gauge_registered(self):
        g = Gauge("test_g")
        assert get_metric("test_g") is g


# ══════════════════════════════════════════════════════════════════════
# Histogram
# ══════════════════════════════════════════════════════════════════════


class TestHistogram:

    def test_histogram_empty(self):
        h = Histogram("test_h")
        snap = h.snapshot()
        assert snap["count"] == 0
        assert snap["sum"] == 0.0
        assert snap["min"] == 0.0
        assert snap["max"] == 0.0
        assert snap["avg"] == 0.0

    def test_histogram_single_value(self):
        h = Histogram("test_h")
        h.observe(5.0)
        snap = h.snapshot()
        assert snap["count"] == 1
        assert snap["sum"] == 5.0
        assert snap["min"] == 5.0
        assert snap["max"] == 5.0
        assert snap["avg"] == 5.0

    def test_histogram_multiple_values(self):
        h = Histogram("test_h")
        h.observe(1.0)
        h.observe(2.0)
        h.observe(3.0)
        snap = h.snapshot()
        assert snap["count"] == 3
        assert snap["sum"] == 6.0
        assert snap["min"] == 1.0
        assert snap["max"] == 3.0
        assert snap["avg"] == 2.0

    def test_histogram_min_max_avg(self):
        h = Histogram("test_h")
        for v in [10, 20, 30, 40, 50]:
            h.observe(v)
        snap = h.snapshot()
        assert snap["min"] == 10.0
        assert snap["max"] == 50.0
        assert snap["avg"] == 30.0

    def test_histogram_count_property(self):
        h = Histogram("test_h")
        h.observe(1)
        h.observe(2)
        assert h.count == 2

    def test_histogram_snapshot_type(self):
        h = Histogram("test_h")
        assert h.snapshot()["type"] == "histogram"

    def test_histogram_registered(self):
        h = Histogram("test_h")
        assert get_metric("test_h") is h


# ══════════════════════════════════════════════════════════════════════
# Registry / snapshot
# ══════════════════════════════════════════════════════════════════════


class TestRegistry:

    def test_snapshot_empty(self):
        assert snapshot() == {}

    def test_snapshot_multiple_metrics(self):
        Counter("a_counter")
        Gauge("b_gauge")
        Histogram("c_hist")
        snap = snapshot()
        assert "a_counter" in snap
        assert "b_gauge" in snap
        assert "c_hist" in snap
        assert snap["a_counter"]["type"] == "counter"
        assert snap["b_gauge"]["type"] == "gauge"
        assert snap["c_hist"]["type"] == "histogram"

    def test_snapshot_sorted_by_name(self):
        Counter("z_last")
        Counter("a_first")
        Counter("m_middle")
        keys = list(snapshot().keys())
        assert keys == ["a_first", "m_middle", "z_last"]

    def test_get_metric_missing(self):
        assert get_metric("nonexistent") is None

    def test_reset_all_clears(self):
        Counter("temp")
        reset_all()
        assert snapshot() == {}
        assert get_metric("temp") is None

    def test_snapshot_reflects_mutations(self):
        c = Counter("mut")
        c.inc(10)
        snap = snapshot()
        assert snap["mut"]["value"] == 10.0
        c.inc(5)
        snap2 = snapshot()
        assert snap2["mut"]["value"] == 15.0


# ══════════════════════════════════════════════════════════════════════
# Default application metrics
# ══════════════════════════════════════════════════════════════════════


class TestDefaultMetrics:
    """Verify the pre-registered application metrics work correctly."""

    @pytest.fixture(autouse=True)
    def _ensure_defaults(self):
        """Re-register module-level defaults if cleared by earlier tests."""
        from importlib import reload
        reset_all()
        reload(metrics)
        yield

    def test_default_metrics_exist(self):
        snap = snapshot()
        expected = {
            "discovery_articles_total",
            "discovery_clusters_stored",
            "analysis_duration_seconds",
            "briefing_sent_total",
            "api_requests_total",
        }
        assert expected.issubset(set(snap.keys()))

    def test_default_counters_are_counters(self):
        snap = snapshot()
        assert snap["discovery_articles_total"]["type"] == "counter"
        assert snap["briefing_sent_total"]["type"] == "counter"

    def test_default_histogram_is_histogram(self):
        snap = snapshot()
        assert snap["analysis_duration_seconds"]["type"] == "histogram"

    def test_module_level_references_work(self):
        """Module-level metric objects can be used directly."""
        before = metrics.api_requests_total.value
        metrics.api_requests_total.inc(1)
        assert metrics.api_requests_total.value == before + 1


# ══════════════════════════════════════════════════════════════════════
# GET /metrics endpoint
# ══════════════════════════════════════════════════════════════════════


class TestMetricsEndpoint:
    """Test the GET /metrics API endpoint.

    Override the autouse fixture — the endpoint reads from the real
    module-level registry.
    """

    @pytest.fixture(autouse=True)
    def _ensure_defaults(self):
        """Re-register module-level defaults if cleared by earlier tests."""
        from importlib import reload
        reset_all()
        reload(metrics)
        yield

    @pytest.fixture()
    def client(self):
        from prism.api.app import create_app
        app = create_app()
        return TestClient(app)

    def test_metrics_returns_200(self, client):
        resp = client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_returns_json(self, client):
        resp = client.get("/metrics")
        data = resp.json()
        assert isinstance(data, dict)

    def test_metrics_contains_defaults(self, client):
        resp = client.get("/metrics")
        data = resp.json()
        assert "discovery_articles_total" in data
        assert "api_requests_total" in data
        assert "analysis_duration_seconds" in data

    def test_metrics_counter_type(self, client):
        resp = client.get("/metrics")
        data = resp.json()
        assert data["discovery_articles_total"]["type"] == "counter"

    def test_metrics_histogram_type(self, client):
        resp = client.get("/metrics")
        data = resp.json()
        assert data["analysis_duration_seconds"]["type"] == "histogram"

    def test_metrics_no_auth_required(self, client):
        """Metrics endpoint should be public (no X-API-Key needed)."""
        resp = client.get("/metrics")
        assert resp.status_code == 200
