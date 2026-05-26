"""T18.2: Graceful degradation when Brave API is down."""

import logging
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from prism.circuit_breaker import CircuitOpenError, brave_breaker
from prism.db import init_db
from prism.metrics import discovery_brave_skip_total, snapshot
from prism.models import Source, StoryCluster


@pytest.fixture()
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def _reset_metric():
    """Reset the brave skip metric between tests."""
    discovery_brave_skip_total._value = 0
    yield
    discovery_brave_skip_total._value = 0


def _seed_rss_source(engine):
    """Create an active source with RSS feed."""
    with Session(engine) as s:
        source = Source(
            name="TestRSS", url="https://rss-source.com",
            rss_url="https://rss-source.com/feed.xml",
            trust_score=0.8, active=True,
        )
        s.add(source)
        s.commit()
        s.refresh(source)
        return source


class TestBraveDegradation:

    def test_rss_only_when_brave_circuit_open(self, db_engine, _reset_metric):
        """Discovery still runs and stores clusters from RSS when Brave is down."""
        from prism.agents.d_ai import DiscoveryAgent

        _seed_rss_source(db_engine)

        # Trip the brave breaker
        for _ in range(5):
            brave_breaker.record_failure()

        rss_article = {
            "title": "RSS Story About Finance",
            "url": "https://rss-source.com/article1",
            "snippet": "Financial markets showed strong growth today.",
            "source": "rss-source.com",
        }

        agent = DiscoveryAgent()
        with patch.object(agent, "fetch_rss_sources", return_value=[rss_article]):
            agent.run_discovery(queries=["test"], engine=db_engine)

        with Session(db_engine) as s:
            clusters = s.exec(select(StoryCluster)).all()
            assert len(clusters) >= 1

    def test_warning_logged_on_brave_skip(self, db_engine, _reset_metric, caplog):
        """Warning is logged when falling back to RSS-only."""
        from prism.agents.d_ai import DiscoveryAgent

        for _ in range(5):
            brave_breaker.record_failure()

        agent = DiscoveryAgent()
        with patch.object(agent, "fetch_rss_sources", return_value=[]):
            with caplog.at_level(logging.WARNING):
                agent.run_discovery(queries=["test"], engine=db_engine)

        assert any(
            "Brave API circuit open" in r.message and "RSS-only" in r.message
            for r in caplog.records
        )

    def test_metric_incremented_on_brave_skip(self, db_engine, _reset_metric):
        """discovery_brave_skip_total is incremented on each skipped cycle."""
        from prism.agents.d_ai import DiscoveryAgent

        for _ in range(5):
            brave_breaker.record_failure()

        agent = DiscoveryAgent()
        with patch.object(agent, "fetch_rss_sources", return_value=[]):
            agent.run_discovery(queries=["q1", "q2"], engine=db_engine)

        # Should only increment once per cycle, not per query
        assert discovery_brave_skip_total._value == 1

    def test_metric_increments_across_cycles(self, db_engine, _reset_metric):
        """Metric increments for each discovery cycle with Brave down."""
        from prism.agents.d_ai import DiscoveryAgent

        for _ in range(5):
            brave_breaker.record_failure()

        agent = DiscoveryAgent()
        with patch.object(agent, "fetch_rss_sources", return_value=[]):
            agent.run_discovery(queries=["q1"], engine=db_engine)
            # Re-trip breaker (reset happens in conftest between tests, but not between calls)
            for _ in range(5):
                brave_breaker.record_failure()
            agent.run_discovery(queries=["q1"], engine=db_engine)

        assert discovery_brave_skip_total._value == 2

    def test_brave_resumes_when_circuit_closes(self, db_engine, _reset_metric):
        """When Brave circuit recovers, next cycle includes Brave results."""
        from prism.agents.d_ai import DiscoveryAgent

        brave_article = {
            "title": "Brave Result",
            "url": "https://news.com/brave1",
            "snippet": "Found via Brave.",
            "source": "news.com",
        }

        agent = DiscoveryAgent()

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": [brave_article]}
        mock_response.raise_for_status = MagicMock()

        # Brave circuit is closed (default after reset) — should call Brave
        with patch.object(agent, "http") as mock_http:
            mock_http.get.return_value = mock_response
            with patch.object(agent, "fetch_rss_sources", return_value=[]):
                agent.run_discovery(queries=["test"], engine=db_engine)

            # Verify Brave was actually called
            assert mock_http.get.call_count >= 1

        # No brave skip metric
        assert discovery_brave_skip_total._value == 0

    def test_brave_skip_metric_in_snapshot(self, db_engine, _reset_metric):
        """discovery_brave_skip_total appears in metrics snapshot."""
        from prism.agents.d_ai import DiscoveryAgent

        for _ in range(5):
            brave_breaker.record_failure()

        agent = DiscoveryAgent()
        with patch.object(agent, "fetch_rss_sources", return_value=[]):
            agent.run_discovery(queries=["q1"], engine=db_engine)

        s = snapshot()
        assert "discovery_brave_skip_total" in s
        assert s["discovery_brave_skip_total"]["value"] == 1

    def test_no_brave_skip_when_circuit_closed(self, db_engine, _reset_metric):
        """When Brave is healthy, no skip metric and Brave is called."""
        from prism.agents.d_ai import DiscoveryAgent

        agent = DiscoveryAgent()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"results": []}
        mock_response.raise_for_status = MagicMock()

        with patch.object(agent, "http") as mock_http:
            mock_http.get.return_value = mock_response
            with patch.object(agent, "fetch_rss_sources", return_value=[]):
                agent.run_discovery(queries=["test"], engine=db_engine)

        assert discovery_brave_skip_total._value == 0
