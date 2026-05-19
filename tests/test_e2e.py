"""T4.2: End-to-end integration test.

Runs the full pipeline discovery -> analysis -> personalization -> delivery
with mocked external APIs but a real SQLite DB.
Verifies DB state at each stage of the state machine.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from prism.db import init_db
from prism.main import analysis_cycle, briefing_cycle, discovery_cycle
from prism.models import (
    Briefing,
    Perspective,
    StoryCluster,
    StoryStatus,
    User,
)
from prism.seed import seed_sources


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


# --- Mock data ---

BRAVE_RESULTS = [
    {
        "title": "Fed holds interest rates steady amid inflation concerns",
        "url": "https://reuters.com/fed-rates-2026",
        "description": "The Federal Reserve kept rates unchanged at its May meeting.",
        "meta_url": {"hostname": "reuters.com"},
    },
    {
        "title": "Tech giants report strong Q2 earnings",
        "url": "https://reuters.com/tech-earnings-q2",
        "description": "Apple, Google, and Microsoft all beat analyst expectations.",
        "meta_url": {"hostname": "reuters.com"},
    },
    {
        "title": "Federal Reserve maintains rates as inflation persists",
        "url": "https://apnews.com/fed-rates-may",
        "description": "AP reports the Fed held steady on rates for the third meeting.",
        "meta_url": {"hostname": "apnews.com"},
    },
]

ANALYSIS_RESPONSE_FED = {
    "headline": "Fed holds rates steady amid inflation concerns",
    "summary": "The Federal Reserve kept interest rates unchanged at its May meeting.",
    "categories": ["finance", "politics"],
    "perspectives": [
        {
            "source_name": "Reuters",
            "source_id": 1,
            "summary": "Reuters frames this as a cautious but expected move.",
            "sentiment": 0.2,
            "bias_label": "center",
            "key_claims": [
                "Fed held rates at 5.25% (Source: Reuters)",
                "Third consecutive meeting without change (Source: Reuters)",
            ],
        },
    ],
}

ANALYSIS_RESPONSE_TECH = {
    "headline": "Tech giants report strong Q2 earnings",
    "summary": "Major tech companies exceeded analyst expectations in Q2.",
    "categories": ["finance", "technology"],
    "perspectives": [
        {
            "source_name": "Reuters",
            "source_id": 1,
            "summary": "Reuters highlights the earnings beat across the sector.",
            "sentiment": 0.7,
            "bias_label": "center",
            "key_claims": [
                "Apple revenue up 12% YoY (Source: Reuters)",
                "Google ad revenue exceeded forecasts (Source: Reuters)",
            ],
        },
    ],
}

BRIEFING_HTML = """\
<h2>Fed holds rates steady</h2>
<p>The Federal Reserve kept rates unchanged (Source: Reuters).</p>
<h2>Tech earnings beat expectations</h2>
<p>Apple revenue up 12% YoY (Source: Reuters).</p>"""


def _mock_brave_response():
    """Return a mock httpx response for Brave API."""
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"results": BRAVE_RESULTS}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


ANALYSIS_RESPONSE_FED_AP = {
    "headline": "Federal Reserve maintains rates as inflation persists",
    "summary": "AP reports the Fed held steady on rates for the third meeting.",
    "categories": ["finance", "politics"],
    "perspectives": [
        {
            "source_name": "AP News",
            "source_id": 1,
            "summary": "AP frames the decision as expected by analysts.",
            "sentiment": 0.1,
            "bias_label": "center",
            "key_claims": [
                "Third consecutive hold on rates (Source: AP News)",
            ],
        },
    ],
}


def _mock_analysis_responses():
    """Return mock Claude responses for analysis — one per cluster."""
    responses = []
    for data in [ANALYSIS_RESPONSE_FED, ANALYSIS_RESPONSE_TECH, ANALYSIS_RESPONSE_FED_AP]:
        msg = MagicMock()
        msg.content = [MagicMock(text=json.dumps(data))]
        responses.append(msg)
    return responses


def test_e2e_single_briefing(db_engine):
    """Full pipeline: seed -> discover -> analyze -> personalize -> deliver."""

    # 1. Seed sources and create a test user
    seed_sources(db_engine)
    with Session(db_engine, expire_on_commit=False) as s:
        user = User(
            email="e2e@test.com",
            interests="finance,technology",
            briefing_depth=5,
        )
        s.add(user)
        s.commit()

    # --- DISCOVERY ---
    with patch("prism.agents.d_ai.httpx.Client") as mock_http_cls:
        mock_http = mock_http_cls.return_value
        mock_http.get.return_value = _mock_brave_response()
        # Mock feedparser to return empty (RSS not needed for this test)
        with patch("prism.agents.d_ai.feedparser.parse") as mock_fp:
            mock_fp.return_value = MagicMock(entries=[], bozo=False)
            discovery_cycle(db_engine)

    # Verify: clusters exist in DB with status=RAW
    with Session(db_engine) as s:
        clusters = s.exec(select(StoryCluster)).all()
        assert len(clusters) >= 1, "Discovery should create at least 1 cluster"
        raw_count = sum(1 for c in clusters if c.status == StoryStatus.RAW)
        assert raw_count == len(clusters), "All clusters should be RAW after discovery"

        # Articles should be linked
        for c in clusters:
            assert c.article_count >= 1

    # --- ANALYSIS ---
    analysis_responses = _mock_analysis_responses()
    with patch("prism.agents.a_ai.anthropic.Anthropic") as mock_anthropic:
        mock_client = mock_anthropic.return_value
        mock_client.messages.create.side_effect = analysis_responses
        analysis_cycle(db_engine)

    # Verify: clusters transition to ANALYZED, perspectives created
    with Session(db_engine) as s:
        clusters = s.exec(select(StoryCluster)).all()
        analyzed = [c for c in clusters if c.status == StoryStatus.ANALYZED]
        assert len(analyzed) >= 1, "At least 1 cluster should be ANALYZED"

        perspectives = s.exec(select(Perspective)).all()
        assert len(perspectives) >= 1, "At least 1 perspective should exist"
        for p in perspectives:
            assert p.source_id is not None
            claims = json.loads(p.key_claims)
            assert len(claims) >= 1

    # --- BRIEFING ---
    mock_briefing_msg = MagicMock()
    mock_briefing_msg.content = [MagicMock(text=BRIEFING_HTML)]

    with patch("prism.agents.w_ai.anthropic.Anthropic") as mock_anthropic:
        mock_client = mock_anthropic.return_value
        mock_client.messages.create.return_value = mock_briefing_msg
        with patch("prism.agents.w_ai.resend") as mock_resend:
            briefing_cycle(db_engine)

    # Verify: briefing stored and marked sent
    with Session(db_engine) as s:
        briefings = s.exec(select(Briefing)).all()
        assert len(briefings) == 1, "One briefing should be created"
        b = briefings[0]
        assert b.story_count >= 1
        assert b.sent is True
        assert b.sent_at is not None
        assert len(b.content_html) > 0

    # Verify: resend was called
    mock_resend.Emails.send.assert_called_once()
    call_arg = mock_resend.Emails.send.call_args[0][0]
    assert call_arg["to"] == ["e2e@test.com"]


def test_e2e_no_unhandled_exceptions(db_engine, caplog):
    """Pipeline handles partial failures without crashing."""
    seed_sources(db_engine)
    with Session(db_engine, expire_on_commit=False) as s:
        user = User(email="robust@test.com", interests="finance")
        s.add(user)
        s.commit()

    # Discovery with Brave API failure — should not crash
    with patch("prism.agents.d_ai.httpx.Client") as mock_http_cls:
        mock_http = mock_http_cls.return_value
        mock_http.get.side_effect = Exception("Brave API down")
        with patch("prism.agents.d_ai.feedparser.parse") as mock_fp:
            mock_fp.return_value = MagicMock(entries=[], bozo=False)
            discovery_cycle(db_engine)  # should not raise

    # Analysis with no clusters — should be a no-op
    analysis_cycle(db_engine)

    # Briefing with no stories — should skip gracefully
    with patch("prism.agents.w_ai.anthropic.Anthropic"):
        with patch("prism.agents.w_ai.resend"):
            briefing_cycle(db_engine)

    with Session(db_engine) as s:
        assert len(s.exec(select(Briefing)).all()) == 0


def test_e2e_state_machine_no_reprocessing(db_engine):
    """ANALYZED clusters are not re-analyzed on second analysis run."""
    seed_sources(db_engine)

    # Discovery
    with patch("prism.agents.d_ai.httpx.Client") as mock_http_cls:
        mock_http = mock_http_cls.return_value
        mock_http.get.return_value = _mock_brave_response()
        with patch("prism.agents.d_ai.feedparser.parse") as mock_fp:
            mock_fp.return_value = MagicMock(entries=[], bozo=False)
            discovery_cycle(db_engine)

    # First analysis
    with patch("prism.agents.a_ai.anthropic.Anthropic") as mock_anthropic:
        mock_client = mock_anthropic.return_value
        mock_client.messages.create.side_effect = _mock_analysis_responses()
        analysis_cycle(db_engine)

    # Second analysis — should not call Claude again (no RAW clusters)
    with patch("prism.agents.a_ai.anthropic.Anthropic") as mock_anthropic:
        mock_client = mock_anthropic.return_value
        analysis_cycle(db_engine)
        assert mock_client.messages.create.call_count == 0
