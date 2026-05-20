"""M1: Discovery Loop tests.

Covers T1.1 (Brave API), T1.2 (RSS), T1.3 (dedup), T1.4 (source registry),
T1.6 (full discovery cycle). Written TDD — tests first.
"""

import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import struct_time
from unittest.mock import MagicMock, patch

import httpx
import pytest
from sqlmodel import Session, select

from prism.agents.d_ai import DiscoveryAgent
from prism.db import init_db
from prism.models import Article, Source, StoryCluster, StoryStatus


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def session(db_engine):
    with Session(db_engine) as s:
        yield s


@pytest.fixture()
def agent():
    """DiscoveryAgent with a mocked httpx client."""
    with patch.object(DiscoveryAgent, "__init__", lambda self: None):
        a = DiscoveryAgent()
        a.http = MagicMock(spec=httpx.Client)
        return a


# --- T1.1: Brave Search API ---

BRAVE_RESPONSE = {
    "results": [
        {
            "title": "Fed raises interest rates by 0.5%",
            "url": "https://reuters.com/fed-rates",
            "description": "The Federal Reserve raised rates...",
            "source": "Reuters",
        },
        {
            "title": "Tech stocks rally after earnings",
            "url": "https://bbc.co.uk/tech-rally",
            "description": "Major tech companies reported...",
            "source": "BBC",
        },
    ]
}


def test_search_brave_returns_results(agent):
    mock_resp = MagicMock()
    mock_resp.json.return_value = BRAVE_RESPONSE
    mock_resp.raise_for_status = MagicMock()
    agent.http.get.return_value = mock_resp

    results = agent.search_brave("finance news", count=10)

    assert len(results) == 2
    assert results[0]["title"] == "Fed raises interest rates by 0.5%"
    assert results[0]["url"] == "https://reuters.com/fed-rates"
    assert results[1]["source"] == "BBC"


def test_search_brave_sends_correct_params(agent):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status = MagicMock()
    agent.http.get.return_value = mock_resp

    agent.search_brave("tech news", count=15)

    agent.http.get.assert_called_once()
    call_kwargs = agent.http.get.call_args
    params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
    assert params["q"] == "tech news"
    assert params["count"] == 15
    assert params["freshness"] == "pd"


def test_search_brave_handles_empty(agent):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"results": []}
    mock_resp.raise_for_status = MagicMock()
    agent.http.get.return_value = mock_resp

    results = agent.search_brave("obscure topic")
    assert results == []


def test_search_brave_handles_rate_limit(agent):
    mock_resp = MagicMock()
    mock_resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "429 Too Many Requests",
        request=MagicMock(),
        response=MagicMock(status_code=429),
    )
    agent.http.get.return_value = mock_resp

    with pytest.raises(httpx.HTTPStatusError):
        agent.search_brave("test")


def test_search_brave_handles_timeout(agent):
    agent.http.get.side_effect = httpx.TimeoutException("Connection timed out")

    with pytest.raises(httpx.TimeoutException):
        agent.search_brave("test")


# --- T1.2: RSS Feed Polling ---

SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Reuters Top News</title>
    <item>
      <title>Oil prices surge amid supply concerns</title>
      <link>https://reuters.com/oil-surge</link>
      <description>Crude oil prices rose sharply...</description>
      <pubDate>Sun, 18 May 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title>EU passes new AI regulation</title>
      <link>https://reuters.com/eu-ai-regulation</link>
      <description>The European Union approved...</description>
      <pubDate>Sun, 18 May 2026 08:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>"""


def test_parse_rss_feed(agent, db_engine):
    with Session(db_engine) as s:
        source = Source(name="Reuters", url="reuters.com",
                        rss_url="https://reuters.com/rss", active=True)
        s.add(source)
        s.commit()

    with patch("prism.agents.d_ai.feedparser") as mock_fp:
        mock_fp.parse.return_value = MagicMock(
            entries=[
                MagicMock(
                    title="Oil prices surge amid supply concerns",
                    link="https://reuters.com/oil-surge",
                    get=lambda k, d="": {
                        "summary": "Crude oil prices rose sharply..."
                    }.get(k, d),
                    published_parsed=(2026, 5, 18, 10, 0, 0, 6, 138, 0),
                ),
                MagicMock(
                    title="EU passes new AI regulation",
                    link="https://reuters.com/eu-ai-regulation",
                    get=lambda k, d="": {
                        "summary": "The European Union approved..."
                    }.get(k, d),
                    published_parsed=(2026, 5, 18, 8, 0, 0, 6, 138, 0),
                ),
            ],
            bozo=False,
        )

        results = agent.fetch_rss_sources(db_engine)

    assert len(results) == 2
    assert results[0]["title"] == "Oil prices surge amid supply concerns"
    assert results[0]["url"] == "https://reuters.com/oil-surge"
    assert results[0]["source"] == "Reuters"


def test_rss_skips_inactive_sources(agent, db_engine):
    with Session(db_engine) as s:
        s.add(Source(name="Inactive", url="inactive.com",
                     rss_url="https://inactive.com/rss", active=False))
        s.commit()

    with patch("prism.agents.d_ai.feedparser") as mock_fp:
        results = agent.fetch_rss_sources(db_engine)

    mock_fp.parse.assert_not_called()
    assert results == []


def test_rss_handles_malformed_feed(agent, db_engine, caplog):
    with Session(db_engine) as s:
        s.add(Source(name="Bad", url="bad.com",
                     rss_url="https://bad.com/rss", active=True))
        s.commit()

    with patch("prism.agents.d_ai.feedparser") as mock_fp:
        mock_fp.parse.return_value = MagicMock(entries=[], bozo=True)
        with caplog.at_level(logging.WARNING):
            results = agent.fetch_rss_sources(db_engine)

    assert results == []
    assert "malformed" in caplog.text.lower() or "bozo" in caplog.text.lower()


def test_rss_dedup_by_url(agent, db_engine):
    """Articles with URLs already in the DB are skipped in RSS results."""
    with Session(db_engine) as s:
        source = Source(name="Reuters", url="reuters.com",
                        rss_url="https://reuters.com/rss", active=True)
        s.add(source)
        s.commit()
        # Pre-existing article
        cluster = StoryCluster(headline="Old", article_count=1)
        s.add(cluster)
        s.commit()
        s.add(Article(cluster_id=cluster.id, source_id=source.id,
                       title="Old article", url="https://reuters.com/oil-surge"))
        s.commit()

    with patch("prism.agents.d_ai.feedparser") as mock_fp:
        mock_fp.parse.return_value = MagicMock(
            entries=[
                MagicMock(
                    title="Oil prices surge",
                    link="https://reuters.com/oil-surge",  # already exists
                    get=lambda k, d="": "",
                    published_parsed=None,
                ),
                MagicMock(
                    title="New story",
                    link="https://reuters.com/new-story",
                    get=lambda k, d="": "",
                    published_parsed=None,
                ),
            ],
            bozo=False,
        )

        results = agent.fetch_rss_sources(db_engine)

    # Only the new URL should be returned
    assert len(results) == 1
    assert results[0]["url"] == "https://reuters.com/new-story"


# --- T1.3: Story Deduplication ---

def test_identical_titles_clustered(agent):
    articles = [
        {"title": "Fed raises rates", "url": "https://a.com/1"},
        {"title": "Fed raises rates", "url": "https://b.com/1"},
    ]
    clusters = agent.deduplicate_articles(articles)
    assert len(clusters) == 1
    assert len(clusters[0]) == 2


def test_similar_titles_clustered(agent):
    articles = [
        {"title": "Fed raises interest rates by half percent", "url": "https://a.com/1"},
        {"title": "Federal Reserve raises interest rates by half percent",
         "url": "https://b.com/1"},
    ]
    clusters = agent.deduplicate_articles(articles)
    assert len(clusters) == 1


def test_unrelated_articles_separate(agent):
    articles = [
        {"title": "Fed raises rates", "url": "https://a.com/1"},
        {"title": "Olympics 2026 opening ceremony details", "url": "https://b.com/1"},
    ]
    clusters = agent.deduplicate_articles(articles)
    assert len(clusters) == 2


def test_empty_input_returns_empty(agent):
    assert agent.deduplicate_articles([]) == []


def test_cross_cycle_merge(agent, db_engine):
    """Articles matching an existing cluster from prior cycle should merge."""
    with Session(db_engine) as s:
        source = Source(name="AP", url="apnews.com")
        s.add(source)
        s.commit()

        old_cluster = StoryCluster(
            headline="Fed raises interest rates to combat inflation",
            article_count=1,
            first_seen=datetime.now(UTC) - timedelta(hours=2),
        )
        s.add(old_cluster)
        s.commit()
        s.add(Article(cluster_id=old_cluster.id, source_id=source.id,
                       title="Fed raises rates", url="https://ap.com/old"))
        s.commit()
        old_id = old_cluster.id

    new_articles = [
        {"title": "Fed raises interest rates to combat rising inflation",
         "url": "https://reuters.com/new-fed", "source": "Reuters",
         "description": "The Fed raised..."},
    ]
    cluster = agent.store_cluster(new_articles, db_engine)
    assert cluster is not None
    assert cluster.id == old_id  # merged into existing
    assert cluster.article_count == 2  # was 1, now 2


def test_cross_cycle_no_merge_after_48h(agent, db_engine):
    """Old clusters (>24h) should not be merged into."""
    with Session(db_engine) as s:
        source = Source(name="AP", url="apnews.com")
        s.add(source)
        s.commit()

        old_cluster = StoryCluster(
            headline="Fed raises interest rates",
            article_count=1,
            first_seen=datetime.now(UTC) - timedelta(hours=48),
        )
        s.add(old_cluster)
        s.commit()
        old_id = old_cluster.id

    new_articles = [
        {"title": "Federal Reserve raises interest rates again",
         "url": "https://reuters.com/fed-new", "source": "Reuters",
         "description": "The Fed raised..."},
    ]
    cluster = agent.store_cluster(new_articles, db_engine)
    assert cluster is not None
    assert cluster.id != old_id  # new cluster created


# --- T1.4: Source Registry ---

def test_new_source_created(agent, db_engine):
    raw = {"url": "https://reuters.com/article/1", "source": "Reuters"}
    with Session(db_engine) as s:
        source = agent._get_or_create_source(s, raw, db_engine)
        assert source.name == "Reuters"
        assert source.url == "reuters.com"
        assert source.trust_score == 0.5
        assert source.bias_label == "unknown"


def test_existing_source_reused(agent, db_engine):
    raw = {"url": "https://reuters.com/article/1", "source": "Reuters"}
    with Session(db_engine) as s:
        s1 = agent._get_or_create_source(s, raw, db_engine)
        s2 = agent._get_or_create_source(s, raw, db_engine)
        assert s1.id == s2.id

    # Only one Source row
    with Session(db_engine) as s:
        count = len(s.exec(select(Source)).all())
        assert count == 1


def test_domain_extraction_www(agent, db_engine):
    raw = {"url": "https://www.reuters.com/article/1", "source": "Reuters"}
    with Session(db_engine) as s:
        source = agent._get_or_create_source(s, raw, db_engine)
        assert source.url == "reuters.com"


def test_domain_extraction_subdomain(agent, db_engine):
    raw = {"url": "https://news.bbc.co.uk/article/1", "source": "BBC"}
    with Session(db_engine) as s:
        source = agent._get_or_create_source(s, raw, db_engine)
        assert source.url == "news.bbc.co.uk"


# --- T1.6: Full Discovery Cycle ---

def test_run_discovery_stores_clusters(agent, db_engine, caplog):
    """Mock Brave + RSS, verify clusters stored in DB."""
    agent.search_brave = MagicMock(return_value=[
        {"title": "Story A", "url": "https://a.com/1",
         "description": "Desc A", "source": "Source A"},
        {"title": "Story B", "url": "https://b.com/1",
         "description": "Desc B", "source": "Source B"},
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])

    with caplog.at_level(logging.INFO):
        agent.run_discovery(queries=["test"], engine=db_engine)

    with Session(db_engine) as s:
        clusters = s.exec(select(StoryCluster)).all()
        articles = s.exec(select(Article)).all()
        assert len(clusters) == 2
        assert len(articles) == 2
        assert all(c.status == StoryStatus.RAW for c in clusters)

    assert "Discovery cycle complete" in caplog.text


def test_run_discovery_handles_api_failure(agent, db_engine, caplog):
    """Brave failure should not block RSS results."""
    agent.search_brave = MagicMock(side_effect=httpx.TimeoutException("timeout"))
    agent.fetch_rss_sources = MagicMock(return_value=[
        {"title": "RSS story", "url": "https://rss.com/1",
         "description": "From RSS", "source": "RSS Source"},
    ])

    with caplog.at_level(logging.INFO):
        agent.run_discovery(queries=["test"], engine=db_engine)

    with Session(db_engine) as s:
        clusters = s.exec(select(StoryCluster)).all()
        assert len(clusters) == 1
        assert clusters[0].headline == "RSS story"


def test_run_discovery_logs_stats(agent, db_engine, caplog):
    agent.search_brave = MagicMock(return_value=[
        {"title": f"Story {i}", "url": f"https://x.com/{i}",
         "description": "d", "source": "X"}
        for i in range(5)
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])

    with caplog.at_level(logging.INFO):
        agent.run_discovery(queries=["test"], engine=db_engine)

    assert "5 clusters" in caplog.text or "Stored 5" in caplog.text


def test_run_discovery_merges_cross_cycle(agent, db_engine):
    """Second discovery run with similar headlines merges into existing clusters."""
    # First run
    agent.search_brave = MagicMock(return_value=[
        {"title": "Fed raises interest rates to combat inflation",
         "url": "https://a.com/1", "description": "d", "source": "A"},
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])
    agent.run_discovery(queries=["test"], engine=db_engine)

    # Second run with similar headline
    agent.search_brave = MagicMock(return_value=[
        {"title": "Fed raises interest rates to combat rising inflation",
         "url": "https://b.com/1", "description": "d", "source": "B"},
    ])
    agent.run_discovery(queries=["test"], engine=db_engine)

    with Session(db_engine) as s:
        clusters = s.exec(select(StoryCluster)).all()
        assert len(clusters) == 1  # merged, not duplicated
        assert clusters[0].article_count == 2


# --- T8.1: published_at propagation ---

def test_store_cluster_sets_published_at_from_iso_string(agent, db_engine):
    """Articles with an ISO published_at string get it stored on the Article row."""
    articles = [
        {"title": "Story with date", "url": "https://x.com/dated",
         "description": "d", "source": "X",
         "published_at": "2026-05-18T10:00:00+00:00"},
    ]
    agent.store_cluster(articles, db_engine)

    with Session(db_engine) as s:
        article = s.exec(select(Article).where(Article.url == "https://x.com/dated")).one()
        assert article.published_at is not None
        assert article.published_at.year == 2026
        assert article.published_at.month == 5
        assert article.published_at.day == 18


def test_store_cluster_sets_published_at_from_datetime(agent, db_engine):
    """Articles with a datetime published_at also work."""
    dt = datetime(2026, 5, 18, 12, 0, 0, tzinfo=UTC)
    articles = [
        {"title": "Story with dt", "url": "https://x.com/dt",
         "description": "d", "source": "X",
         "published_at": dt},
    ]
    agent.store_cluster(articles, db_engine)

    with Session(db_engine) as s:
        article = s.exec(select(Article).where(Article.url == "https://x.com/dt")).one()
        assert article.published_at is not None
        assert article.published_at.hour == 12


def test_store_cluster_handles_missing_published_at(agent, db_engine):
    """Articles without published_at get None — no crash."""
    articles = [
        {"title": "No date story", "url": "https://x.com/nodate",
         "description": "d", "source": "X"},
    ]
    agent.store_cluster(articles, db_engine)

    with Session(db_engine) as s:
        article = s.exec(select(Article).where(Article.url == "https://x.com/nodate")).one()
        assert article.published_at is None


def test_rss_published_at_round_trips(agent, db_engine):
    """RSS articles with published_parsed end up with published_at in the DB."""
    with Session(db_engine) as s:
        s.add(Source(name="Reuters", url="reuters.com",
                     rss_url="https://reuters.com/rss", active=True))
        s.commit()

    with patch("prism.agents.d_ai.feedparser") as mock_fp:
        mock_fp.parse.return_value = MagicMock(
            entries=[
                MagicMock(
                    title="Dated RSS story",
                    link="https://reuters.com/dated-rss",
                    get=lambda k, d="": {"summary": "desc"}.get(k, d),
                    published_parsed=struct_time((2026, 5, 18, 10, 0, 0, 6, 138, 0)),
                ),
            ],
            bozo=False,
        )
        rss_articles = agent.fetch_rss_sources(db_engine)

    # Store the RSS articles
    agent.store_cluster(rss_articles, db_engine)

    with Session(db_engine) as s:
        article = s.exec(
            select(Article).where(Article.url == "https://reuters.com/dated-rss")
        ).one()
        assert article.published_at is not None
        assert article.published_at.year == 2026
        assert article.published_at.month == 5


# --- T8.2: Brave published_at parsing ---

class TestParseBraveAge:
    def test_hours_ago(self, agent):
        dt = agent._parse_brave_age("5 hours ago")
        assert dt is not None
        delta = datetime.now(UTC) - dt
        assert 4.9 * 3600 <= delta.total_seconds() <= 5.1 * 3600

    def test_minutes_ago(self, agent):
        dt = agent._parse_brave_age("30 minutes ago")
        assert dt is not None
        delta = datetime.now(UTC) - dt
        assert 29 * 60 <= delta.total_seconds() <= 31 * 60

    def test_days_ago(self, agent):
        dt = agent._parse_brave_age("2 days ago")
        assert dt is not None
        delta = datetime.now(UTC) - dt
        assert 1.9 * 86400 <= delta.total_seconds() <= 2.1 * 86400

    def test_weeks_ago(self, agent):
        dt = agent._parse_brave_age("1 week ago")
        assert dt is not None
        delta = datetime.now(UTC) - dt
        assert 6.9 * 86400 <= delta.total_seconds() <= 7.1 * 86400

    def test_singular_unit(self, agent):
        dt = agent._parse_brave_age("1 hour ago")
        assert dt is not None

    def test_invalid_string(self, agent):
        assert agent._parse_brave_age("just now") is None
        assert agent._parse_brave_age("") is None
        assert agent._parse_brave_age("yesterday") is None


class TestNormalizeBraveResults:
    def test_adds_published_at_from_age(self, agent):
        results = [
            {"title": "Story", "url": "https://x.com/1", "age": "3 hours ago"},
        ]
        normalized = agent._normalize_brave_results(results)
        assert "published_at" in normalized[0]
        assert normalized[0]["published_at"] is not None

    def test_skips_when_published_at_already_set(self, agent):
        results = [
            {"title": "Story", "url": "https://x.com/1",
             "age": "3 hours ago", "published_at": "2026-05-18T10:00:00+00:00"},
        ]
        normalized = agent._normalize_brave_results(results)
        assert normalized[0]["published_at"] == "2026-05-18T10:00:00+00:00"

    def test_handles_missing_age(self, agent):
        results = [
            {"title": "Story", "url": "https://x.com/1"},
        ]
        normalized = agent._normalize_brave_results(results)
        assert "published_at" not in normalized[0] or normalized[0].get("published_at") is None

    def test_handles_unparseable_age(self, agent):
        results = [
            {"title": "Story", "url": "https://x.com/1", "age": "just now"},
        ]
        normalized = agent._normalize_brave_results(results)
        assert normalized[0].get("published_at") is None


def test_brave_published_at_round_trips(agent, db_engine):
    """Brave results with age field end up with published_at in the DB."""
    agent.search_brave = MagicMock(return_value=[
        {"title": "Brave story", "url": "https://brave.com/story1",
         "description": "d", "source": "Brave Source", "age": "2 hours ago"},
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])

    agent.run_discovery(queries=["test"], engine=db_engine)

    with Session(db_engine) as s:
        article = s.exec(
            select(Article).where(Article.url == "https://brave.com/story1")
        ).one()
        assert article.published_at is not None
        delta = datetime.now(UTC) - article.published_at.replace(tzinfo=UTC)
        assert 1.5 * 3600 <= delta.total_seconds() <= 2.5 * 3600


# --- T8.3: max_stories_per_cycle enforcement ---

def test_run_discovery_respects_max_stories(agent, db_engine):
    """Only max_stories_per_cycle clusters are stored, largest first."""
    # Generate 15 articles with completely different titles so each is its own cluster
    distinct_titles = [
        "Fed raises interest rates", "Olympics opening ceremony details",
        "Hurricane warning issued coastal areas", "Mars rover discovers minerals",
        "Parliament votes on trade agreement", "Earthquake strikes remote island",
        "Vaccine trial shows promising results", "Stock market hits record high",
        "Wildfire evacuations ordered mountain region", "New species discovered rainforest",
        "Submarine cable damaged disrupting internet", "Solar eclipse visible northern hemisphere",
        "Central bank announces policy change", "Archaeological dig reveals ancient city",
        "Satellite launch successful orbit achieved",
    ]
    agent.search_brave = MagicMock(return_value=[
        {"title": t, "url": f"https://x.com/{i}",
         "description": "d", "source": "X"}
        for i, t in enumerate(distinct_titles)
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])

    with patch("prism.agents.d_ai.settings") as mock_settings:
        mock_settings.max_stories_per_cycle = 5
        mock_settings.brave_api_key = "test"
        agent.run_discovery(queries=["test"], engine=db_engine)

    with Session(db_engine) as s:
        clusters = s.exec(select(StoryCluster)).all()
        assert len(clusters) == 5


def test_run_discovery_no_truncation_under_limit(agent, db_engine):
    """All clusters stored when count is under the limit."""
    agent.search_brave = MagicMock(return_value=[
        {"title": f"Story {i}", "url": f"https://x.com/{i}",
         "description": "d", "source": "X"}
        for i in range(3)
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])

    with patch("prism.agents.d_ai.settings") as mock_settings:
        mock_settings.max_stories_per_cycle = 50
        mock_settings.brave_api_key = "test"
        agent.run_discovery(queries=["test"], engine=db_engine)

    with Session(db_engine) as s:
        clusters = s.exec(select(StoryCluster)).all()
        assert len(clusters) == 3


def test_run_discovery_prefers_larger_clusters(agent, db_engine):
    """When truncating, clusters with more articles survive."""
    # 2 articles that cluster together + 3 singletons = 4 clusters
    articles = [
        {"title": "Fed raises rates sharply", "url": "https://a.com/1",
         "description": "d", "source": "A"},
        {"title": "Fed raises rates sharply today", "url": "https://b.com/1",
         "description": "d", "source": "B"},
        {"title": "Olympics opening ceremony", "url": "https://c.com/1",
         "description": "d", "source": "C"},
        {"title": "New AI model released", "url": "https://d.com/1",
         "description": "d", "source": "D"},
        {"title": "Weather forecast update", "url": "https://e.com/1",
         "description": "d", "source": "E"},
    ]
    agent.search_brave = MagicMock(return_value=articles)
    agent.fetch_rss_sources = MagicMock(return_value=[])

    with patch("prism.agents.d_ai.settings") as mock_settings:
        mock_settings.max_stories_per_cycle = 2
        mock_settings.brave_api_key = "test"
        agent.run_discovery(queries=["test"], engine=db_engine)

    with Session(db_engine) as s:
        clusters = s.exec(
            select(StoryCluster).order_by(StoryCluster.article_count.desc())  # type: ignore[union-attr]
        ).all()
        assert len(clusters) == 2
        # The 2-article Fed cluster should be first (largest)
        assert clusters[0].article_count == 2


# --- T9.1: Cross-cycle merge after analysis rewrites headline ---

def test_cross_cycle_merge_after_analysis_rewrite(agent, db_engine):
    """Merge still works when A_AI has rewritten the cluster headline.

    This is the core bug: after analysis, cluster.headline is Claude's
    neutral rephrasing which has low Jaccard similarity to raw article
    titles. The fix compares against stored article titles too.
    """
    with Session(db_engine) as s:
        source = Source(name="Reuters", url="reuters.com")
        s.add(source)
        s.commit()

        # Simulate a cluster that has already been analyzed
        cluster = StoryCluster(
            headline="Federal Reserve maintains benchmark rate amid persistent inflation",
            article_count=1,
            status=StoryStatus.ANALYZED,
            first_seen=datetime.now(UTC) - timedelta(hours=3),
        )
        s.add(cluster)
        s.commit()

        # The original article title is very different from Claude's headline
        s.add(Article(
            cluster_id=cluster.id, source_id=source.id,
            title="Fed holds rates steady at May meeting",
            url="https://reuters.com/fed-may",
        ))
        s.commit()
        old_id = cluster.id

    # New article with title similar to the ORIGINAL article, not the rewritten headline
    new_articles = [
        {"title": "Fed holds interest rates steady at latest meeting",
         "url": "https://apnews.com/fed-steady", "source": "AP",
         "description": "The Federal Reserve held rates..."},
    ]
    result = agent.store_cluster(new_articles, db_engine)
    assert result is not None
    assert result.id == old_id, "Should merge into existing cluster via article title match"
    assert result.article_count == 2


def test_cross_cycle_merge_still_works_on_headline(agent, db_engine):
    """Pre-analysis clusters (headline = raw title) still merge normally."""
    with Session(db_engine) as s:
        source = Source(name="Reuters", url="reuters.com")
        s.add(source)
        s.commit()

        cluster = StoryCluster(
            headline="Fed holds rates steady at May meeting",
            article_count=1,
            status=StoryStatus.RAW,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        s.add(cluster)
        s.commit()
        s.add(Article(
            cluster_id=cluster.id, source_id=source.id,
            title="Fed holds rates steady at May meeting",
            url="https://reuters.com/fed-1",
        ))
        s.commit()
        old_id = cluster.id

    new_articles = [
        {"title": "Fed holds interest rates steady at May meeting today",
         "url": "https://bbc.com/fed", "source": "BBC",
         "description": "d"},
    ]
    result = agent.store_cluster(new_articles, db_engine)
    assert result is not None
    assert result.id == old_id


def test_cross_cycle_no_false_merge_on_unrelated_articles(agent, db_engine):
    """Unrelated articles in a cluster don't cause false merges."""
    with Session(db_engine) as s:
        source = Source(name="Reuters", url="reuters.com")
        s.add(source)
        s.commit()

        cluster = StoryCluster(
            headline="Markets overview and economic indicators",
            article_count=1,
            first_seen=datetime.now(UTC) - timedelta(hours=2),
        )
        s.add(cluster)
        s.commit()
        s.add(Article(
            cluster_id=cluster.id, source_id=source.id,
            title="Stock market closes higher on earnings",
            url="https://reuters.com/stocks",
        ))
        s.commit()
        old_id = cluster.id

    # Completely unrelated article
    new_articles = [
        {"title": "Hurricane warning issued for coastal areas",
         "url": "https://weather.com/hurricane", "source": "Weather",
         "description": "d"},
    ]
    result = agent.store_cluster(new_articles, db_engine)
    assert result is not None
    assert result.id != old_id, "Unrelated article should create a new cluster"


# --- T9.5: Zero-result alerting ---

def test_run_discovery_alerts_on_zero_articles(agent, db_engine):
    """Alert fired when both Brave and RSS return nothing."""
    agent.search_brave = MagicMock(return_value=[])
    agent.fetch_rss_sources = MagicMock(return_value=[])

    with patch("prism.agents.d_ai.send_alert") as mock_alert:
        agent.run_discovery(queries=["test"], engine=db_engine)

    mock_alert.assert_called_once()
    assert "zero articles" in mock_alert.call_args[0][0].lower()


def test_run_discovery_alerts_on_zero_stored(agent, db_engine):
    """Alert fired when articles found but store_cluster returns None for all."""
    agent.search_brave = MagicMock(return_value=[
        {"title": "Story", "url": "https://a.com/1",
         "description": "d", "source": "A"},
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])
    agent.store_cluster = MagicMock(return_value=None)

    with patch("prism.agents.d_ai.send_alert") as mock_alert:
        agent.run_discovery(queries=["test"], engine=db_engine)

    mock_alert.assert_called_once()
    assert "stored 0" in mock_alert.call_args[0][0].lower()


def test_run_discovery_no_alert_on_success(agent, db_engine):
    """No alert when discovery stores clusters normally."""
    agent.search_brave = MagicMock(return_value=[
        {"title": "Fresh story", "url": "https://a.com/1",
         "description": "d", "source": "A"},
    ])
    agent.fetch_rss_sources = MagicMock(return_value=[])

    with patch("prism.agents.d_ai.send_alert") as mock_alert:
        agent.run_discovery(queries=["test"], engine=db_engine)

    mock_alert.assert_not_called()
