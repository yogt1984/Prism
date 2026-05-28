"""M2: Analysis Pipeline tests.

Covers T2.1 (token budget), T2.2 (cluster analysis), T2.3 (perspective storage),
T2.4 (batch processing). Written TDD.
"""

import json
import logging
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from prism.agents.a_ai import AnalysisAgent
from prism.db import init_db
from prism.metrics import reset_all as reset_metrics, resonance_computed_total
from prism.models import (
    Article,
    BiasLabel,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    TopicResonance,
)


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


def _seed_cluster(session: Session, n_articles: int = 3) -> StoryCluster:
    """Helper: create a source, cluster, and N articles."""
    source = Source(name="Reuters", url="reuters.com", trust_score=0.9)
    session.add(source)
    session.commit()

    cluster = StoryCluster(headline="Test event", article_count=n_articles)
    session.add(cluster)
    session.commit()

    for i in range(n_articles):
        session.add(Article(
            cluster_id=cluster.id,
            source_id=source.id,
            title=f"Article {i}",
            url=f"https://reuters.com/{i}",
            snippet=f"This is the snippet for article {i} with some details.",
        ))
    session.commit()
    session.refresh(cluster)
    return cluster


MOCK_ANALYSIS_RESPONSE = {
    "headline": "Markets rally on Fed decision",
    "summary": "Stock markets rose after the Federal Reserve held rates steady.",
    "categories": ["finance", "politics"],
    "perspectives": [
        {
            "source_name": "Reuters",
            "source_id": 1,
            "summary": "Reuters frames this as a market relief rally",
            "sentiment": 0.6,
            "bias_label": "center",
            "key_claims": [
                "S&P 500 rose 2.1% (Source: Reuters)",
                "Fed held rates at 5.25% (Source: Reuters)",
            ],
        },
    ],
}


def _make_mock_agent():
    """Create an AnalysisAgent with mocked Claude client."""
    with patch.object(AnalysisAgent, "__init__", lambda self: None):
        agent = AnalysisAgent()
        agent.client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=json.dumps(MOCK_ANALYSIS_RESPONSE))]
        agent.client.messages.create.return_value = mock_msg
        return agent


# --- T2.1: Token Budget and Truncation ---

def test_truncate_respects_budget():
    articles = [
        {"title": "Short", "url": "https://x.com/1", "snippet": "A" * 5000},
        {"title": "Short", "url": "https://x.com/2", "snippet": "B" * 5000},
    ]
    # Budget: 500 tokens = 2000 chars. Base ~ 2*(5+15+50) = 140.
    # Snippet budget ~ 1860, per article ~ 930.
    result = AnalysisAgent._truncate_articles(articles, max_tokens=500)
    for a in result:
        assert len(a["snippet"]) < 2000  # well under budget
        assert a["snippet"].endswith("...")


def test_truncate_preserves_all_short():
    articles = [
        {"title": "Title A", "url": "https://x.com/1", "snippet": "Short snippet"},
        {"title": "Title B", "url": "https://x.com/2", "snippet": "Another short one"},
    ]
    result = AnalysisAgent._truncate_articles(articles, max_tokens=8000)
    assert result[0]["snippet"] == "Short snippet"
    assert result[1]["snippet"] == "Another short one"


def test_truncate_keeps_title_and_url():
    articles = [
        {"title": "Important Title", "url": "https://important.com/1",
         "snippet": "X" * 10000},
    ]
    result = AnalysisAgent._truncate_articles(articles, max_tokens=100)
    assert result[0]["title"] == "Important Title"
    assert result[0]["url"] == "https://important.com/1"


def test_truncate_distributes_evenly():
    articles = [
        {"title": "T", "url": "https://x.com/1", "snippet": "A" * 5000},
        {"title": "T", "url": "https://x.com/2", "snippet": "B" * 5000},
        {"title": "T", "url": "https://x.com/3", "snippet": "C" * 5000},
    ]
    result = AnalysisAgent._truncate_articles(articles, max_tokens=1000)
    lengths = [len(a["snippet"]) for a in result]
    # All should be roughly equal (within 10 chars due to "..." suffix)
    assert max(lengths) - min(lengths) <= 10


# --- T2.2: Cluster Analysis via Claude ---

def test_analyze_cluster_parses_json(db_engine):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        perspectives = s.exec(select(Perspective)).all()
        assert len(perspectives) == 1
        assert perspectives[0].summary == "Reuters frames this as a market relief rally"


def test_analyze_cluster_extracts_headline(db_engine):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        cluster = s.get(StoryCluster, cluster_id)
        assert cluster.headline == "Markets rally on Fed decision"


def test_analyze_cluster_assigns_categories(db_engine):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        cluster = s.get(StoryCluster, cluster_id)
        assert "finance" in cluster.categories
        assert "politics" in cluster.categories


def test_analyze_cluster_handles_bad_json(db_engine, caplog):
    agent = _make_mock_agent()
    # Override to return invalid JSON
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text="not valid json {{{")]
    agent.client.messages.create.return_value = mock_msg

    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    with caplog.at_level(logging.ERROR):
        agent.analyze_cluster(cluster_id, db_engine)

    assert "Failed to parse" in caplog.text
    # Cluster should remain RAW
    with Session(db_engine) as s:
        cluster = s.get(StoryCluster, cluster_id)
        assert cluster.status == StoryStatus.RAW


def test_analyze_cluster_skips_empty(db_engine, caplog):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = StoryCluster(headline="Empty", article_count=0)
        s.add(cluster)
        s.commit()
        cluster_id = cluster.id

    with caplog.at_level(logging.WARNING):
        agent.analyze_cluster(cluster_id, db_engine)

    assert "no articles" in caplog.text.lower()
    # Claude should NOT have been called
    agent.client.messages.create.assert_not_called()


def test_analyze_cluster_status_transitions(db_engine):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        cluster = s.get(StoryCluster, cluster_id)
        assert cluster.status == StoryStatus.ANALYZED


# --- T2.3: Perspective Storage and Attribution ---

def test_perspective_links_to_source(db_engine):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        perspectives = s.exec(select(Perspective)).all()
        for p in perspectives:
            source = s.get(Source, p.source_id)
            assert source is not None, f"Perspective {p.id} has orphaned source_id"


def test_key_claims_are_valid_json(db_engine):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        perspectives = s.exec(select(Perspective)).all()
        for p in perspectives:
            claims = json.loads(p.key_claims)
            assert isinstance(claims, list)
            assert len(claims) > 0


def test_sentiment_clamped(db_engine):
    """Sentiment values outside [-1, 1] should be clamped."""
    agent = _make_mock_agent()
    # Override with out-of-range sentiment
    extreme_response = {
        **MOCK_ANALYSIS_RESPONSE,
        "perspectives": [{
            "source_name": "Test",
            "source_id": 1,
            "summary": "Extreme sentiment",
            "sentiment": 5.0,  # out of range
            "bias_label": "center",
            "key_claims": ["claim (Source: Test)"],
        }],
    }
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(extreme_response))]
    agent.client.messages.create.return_value = mock_msg

    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        p = s.exec(select(Perspective)).one()
        assert -1.0 <= p.sentiment <= 1.0


def test_invalid_bias_label_mapped_to_unknown(db_engine):
    """Unrecognized bias labels from Claude should map to UNKNOWN."""
    agent = _make_mock_agent()
    bad_bias_response = {
        **MOCK_ANALYSIS_RESPONSE,
        "perspectives": [{
            "source_name": "Test",
            "source_id": 1,
            "summary": "Bad bias",
            "sentiment": 0.0,
            "bias_label": "extremely_biased",  # invalid
            "key_claims": ["claim (Source: Test)"],
        }],
    }
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(bad_bias_response))]
    agent.client.messages.create.return_value = mock_msg

    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        p = s.exec(select(Perspective)).one()
        assert p.bias_label == BiasLabel.UNKNOWN


# --- T2.4: Batch Processing ---

def test_process_pending_finds_raw_only(db_engine):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        _seed_cluster(s)
        # Create an already-analyzed cluster
        analyzed = StoryCluster(
            headline="Already done",
            article_count=0,
            status=StoryStatus.ANALYZED,
        )
        s.add(analyzed)
        s.commit()

    agent.process_pending(db_engine)

    # Claude should be called only once (for the RAW cluster)
    assert agent.client.messages.create.call_count == 1


def test_process_pending_handles_failure(db_engine, caplog):
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        _seed_cluster(s)
        # Create a second cluster
        source = s.exec(select(Source)).first()
        c2 = StoryCluster(headline="Second", article_count=1)
        s.add(c2)
        s.commit()
        s.add(Article(
            cluster_id=c2.id, source_id=source.id,
            title="Art2", url="https://x.com/99",
        ))
        s.commit()

    # First call fails, second succeeds
    good_msg = MagicMock()
    good_msg.content = [MagicMock(text=json.dumps(MOCK_ANALYSIS_RESPONSE))]
    agent.client.messages.create.side_effect = [
        Exception("API error"),
        good_msg,
    ]

    with caplog.at_level(logging.ERROR):
        agent.process_pending(db_engine)

    assert "Failed to analyze" in caplog.text
    # Second cluster should still have been processed
    with Session(db_engine) as s:
        analyzed = s.exec(
            select(StoryCluster).where(
                StoryCluster.status == StoryStatus.ANALYZED
            )
        ).all()
        assert len(analyzed) == 1


def test_process_pending_delays_calls(db_engine):
    """Verify there's a delay between Claude API calls."""
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        _seed_cluster(s)
        source = s.exec(select(Source)).first()
        c2 = StoryCluster(headline="Second", article_count=1)
        s.add(c2)
        s.commit()
        s.add(Article(
            cluster_id=c2.id, source_id=source.id,
            title="Art2", url="https://x.com/99",
        ))
        s.commit()

    with patch("prism.agents.a_ai.time.sleep") as mock_sleep:
        agent.process_pending(db_engine)

    # sleep(1) called between the two clusters
    mock_sleep.assert_called_with(1)


# --- T8.4: Sort articles by source trust, not source_id ---

def test_analyze_cluster_sorts_by_trust(db_engine):
    """Articles from higher-trust sources appear first in the Claude prompt."""
    agent = _make_mock_agent()

    with Session(db_engine) as s:
        low_trust = Source(name="Tabloid", url="tabloid.com", trust_score=0.2)
        high_trust = Source(name="Reuters", url="reuters.com", trust_score=0.95)
        s.add(low_trust)
        s.add(high_trust)
        s.commit()

        cluster = StoryCluster(headline="Test", article_count=2)
        s.add(cluster)
        s.commit()

        # Low-trust article has lower source_id (created first)
        s.add(Article(
            cluster_id=cluster.id, source_id=low_trust.id,
            title="Tabloid take", url="https://tabloid.com/1",
            snippet="Low trust content",
        ))
        s.add(Article(
            cluster_id=cluster.id, source_id=high_trust.id,
            title="Reuters report", url="https://reuters.com/1",
            snippet="High trust content",
        ))
        s.commit()
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    # Check the prompt sent to Claude — high-trust article should come first
    call_args = agent.client.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    reuters_pos = prompt.index("Reuters report")
    tabloid_pos = prompt.index("Tabloid take")
    assert reuters_pos < tabloid_pos, "High-trust articles should appear before low-trust"


def test_analyze_cluster_caps_at_15_by_trust(db_engine):
    """When >15 articles, only the 15 highest-trust are sent to Claude."""
    agent = _make_mock_agent()

    with Session(db_engine) as s:
        sources = []
        for i in range(20):
            src = Source(
                name=f"Source-{i}", url=f"source{i}.com",
                trust_score=i / 20,  # 0.0 to 0.95
            )
            s.add(src)
            sources.append(src)
        s.commit()

        cluster = StoryCluster(headline="Big story", article_count=20)
        s.add(cluster)
        s.commit()

        for i, src in enumerate(sources):
            s.add(Article(
                cluster_id=cluster.id, source_id=src.id,
                title=f"Article-src{i:02d}", url=f"https://s{i}.com/1",
                snippet=f"Content from source {i}",
            ))
        s.commit()
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    # The 5 lowest-trust sources (0-4) should be excluded from the prompt
    call_args = agent.client.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    for i in range(5):
        assert f"Article-src{i:02d}" not in prompt, (
            f"Source-{i} (trust={i/20:.2f}) should have been excluded"
        )
    # The highest-trust sources should be included
    for i in range(15, 20):
        assert f"Article-src{i:02d}" in prompt


# --- T9.4: Enforce max_perspectives_per_story ---

def test_perspectives_capped_at_config_limit(db_engine):
    """Claude returns 8 perspectives but only max_perspectives_per_story are stored."""
    agent = _make_mock_agent()

    many_perspectives = [
        {
            "source_name": f"Outlet-{i}",
            "source_id": 1,
            "summary": f"Perspective from outlet {i}",
            "sentiment": 0.1 * i,
            "bias_label": "center",
            "key_claims": [f"Claim {i} (Source: Outlet-{i})"],
        }
        for i in range(8)
    ]
    response = {**MOCK_ANALYSIS_RESPONSE, "perspectives": many_perspectives}
    mock_msg = MagicMock()
    mock_msg.content = [MagicMock(text=json.dumps(response))]
    agent.client.messages.create.return_value = mock_msg

    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        stored = s.exec(select(Perspective)).all()
        # max_perspectives_per_story = 5
        assert len(stored) == 5
        # First 5 perspectives should be kept (order preserved)
        summaries = [p.summary for p in stored]
        assert summaries[0] == "Perspective from outlet 0"
        assert summaries[4] == "Perspective from outlet 4"


# --- T-RES.5: Resonance wired into A_AI ---


@pytest.fixture(autouse=True)
def _reset_metrics_fixture():
    reset_metrics()
    yield


def test_analyze_cluster_creates_resonance(db_engine):
    """After analyze_cluster, a TopicResonance row exists for that cluster."""
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        tr = s.exec(
            select(TopicResonance).where(TopicResonance.cluster_id == cluster_id)
        ).first()
        assert tr is not None
        assert tr.resonance > 0.0
        assert tr.mention_count == 3  # _seed_cluster creates 3 articles
        assert tr.source_count == 1  # all from same source


def test_resonance_score_matches_cluster(db_engine):
    """StoryCluster.resonance_score matches TopicResonance.resonance."""
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        cluster = s.get(StoryCluster, cluster_id)
        tr = s.exec(
            select(TopicResonance).where(TopicResonance.cluster_id == cluster_id)
        ).first()
        assert cluster.resonance_score == tr.resonance


def test_reanalysis_updates_resonance(db_engine):
    """Re-running analysis on the same cluster updates (not duplicates) the resonance row."""
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    agent.analyze_cluster(cluster_id, db_engine)

    # Reset status to RAW so we can re-analyze
    with Session(db_engine) as s:
        cluster = s.get(StoryCluster, cluster_id)
        cluster.status = StoryStatus.RAW
        s.add(cluster)
        s.commit()

    agent.analyze_cluster(cluster_id, db_engine)

    with Session(db_engine) as s:
        rows = s.exec(
            select(TopicResonance).where(TopicResonance.cluster_id == cluster_id)
        ).all()
        assert len(rows) == 1  # updated, not duplicated


def test_resonance_metric_increments(db_engine):
    """resonance_computed_total counter increments on each computation."""
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    before = resonance_computed_total.value
    agent.analyze_cluster(cluster_id, db_engine)
    assert resonance_computed_total.value == before + 1


def test_resonance_failure_does_not_block_analysis(db_engine, caplog):
    """Resonance computation failure does not block analysis."""
    agent = _make_mock_agent()
    with Session(db_engine) as s:
        cluster = _seed_cluster(s)
        cluster_id = cluster.id

    with patch(
        "prism.agents.a_ai.compute_resonance",
        side_effect=RuntimeError("boom"),
    ):
        with caplog.at_level(logging.ERROR):
            agent.analyze_cluster(cluster_id, db_engine)

    # Analysis should still have completed
    with Session(db_engine) as s:
        cluster = s.get(StoryCluster, cluster_id)
        assert cluster.status == StoryStatus.ANALYZED
    assert "Resonance computation failed" in caplog.text
