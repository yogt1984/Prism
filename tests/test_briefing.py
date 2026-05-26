"""M3: Personalization + Briefing Delivery tests.

Covers T3.1 (scoring extensions), T3.2 (story selection with DB),
T3.3 (briefing generation), T3.4 (email delivery), T3.5 (storage/tracking).
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session, select

from prism.agents.p_ai import PersonalizationAgent
from prism.agents.w_ai import WriterAgent
from prism.db import init_db
from prism.models import (
    Briefing,
    BriefingFormat,
    Engagement,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    User,
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


def _seed_analyzed_clusters(
    session: Session, n: int = 5, age_hours: float = 2.0,
) -> list[StoryCluster]:
    """Create source + N analyzed clusters with perspectives."""
    source = Source(name="Reuters", url="reuters.com", trust_score=0.9)
    session.add(source)
    session.commit()

    clusters = []
    categories = ["finance", "politics", "technology", "sports", "science"]
    for i in range(n):
        c = StoryCluster(
            headline=f"Story {i}: {categories[i % len(categories)]} news",
            summary=f"Summary of story {i}",
            categories=categories[i % len(categories)],
            status=StoryStatus.ANALYZED,
            article_count=2 + i,
            first_seen=datetime.now(UTC) - timedelta(hours=age_hours),
        )
        session.add(c)
        session.commit()

        session.add(Perspective(
            cluster_id=c.id,
            source_id=source.id,
            summary=f"Reuters perspective on story {i}",
            sentiment=0.1 * i,
            key_claims=json.dumps([f"Claim {i} (Source: Reuters)"]),
        ))
        session.commit()
        clusters.append(c)

    return clusters


# --- T3.1: Scoring Extensions ---

def test_score_diversity_bonus():
    p_ai = PersonalizationAgent()
    user = User(email="t@t.com", interests="")
    c = StoryCluster(
        categories="", article_count=6,
        first_seen=datetime.now(UTC) - timedelta(hours=30),
    )
    score = p_ai.score_story(c, user)
    # No interest (0) + recency >24h (0) + diversity 6*0.5=3.0
    assert score == 3.0


def test_score_diversity_capped():
    p_ai = PersonalizationAgent()
    user = User(email="t@t.com", interests="")
    c = StoryCluster(
        categories="", article_count=20,
        first_seen=datetime.now(UTC) - timedelta(hours=30),
    )
    score = p_ai.score_story(c, user)
    # diversity 20*0.5=10.0 but capped at 3.0
    assert score == 3.0


def test_score_empty_interests():
    p_ai = PersonalizationAgent()
    user = User(email="t@t.com", interests="")
    c = StoryCluster(
        categories="finance", article_count=1,
        first_seen=datetime.now(UTC) - timedelta(hours=1),
    )
    score = p_ai.score_story(c, user)
    # No interest match (0) + recency <6h (3.0) + diversity 0.5
    assert score == 3.5


def test_score_multiple_interest_match():
    p_ai = PersonalizationAgent()
    user = User(email="t@t.com", interests="finance,technology,politics")
    c = StoryCluster(
        categories="finance,technology",
        article_count=1,
        first_seen=datetime.now(UTC) - timedelta(hours=30),
    )
    score = p_ai.score_story(c, user)
    # 2 matches * 5.0 = 10.0 + recency 0 + diversity 0.5
    assert score == 10.5


# --- T3.2: Story Selection ---

def test_select_excludes_seen_stories(db_engine):
    p_ai = PersonalizationAgent()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=3, age_hours=2.0)
        user = User(email="alice@test.com", interests="finance")
        s.add(user)
        s.commit()
        # Mark first cluster as seen
        s.add(Engagement(
            user_id=user.id, cluster_id=clusters[0].id, action="read",
        ))
        s.commit()

    result = p_ai.select_stories(user, db_engine)
    result_ids = {c.id for c in result}
    assert clusters[0].id not in result_ids


def test_select_respects_briefing_depth(db_engine):
    p_ai = PersonalizationAgent()
    with Session(db_engine, expire_on_commit=False) as s:
        _seed_analyzed_clusters(s, n=10, age_hours=2.0)
        user = User(email="bob@test.com", interests="finance", briefing_depth=3, is_pro=True)
        s.add(user)
        s.commit()

    result = p_ai.select_stories(user, db_engine)
    assert len(result) == 3


def test_select_returns_sorted(db_engine):
    p_ai = PersonalizationAgent()
    with Session(db_engine, expire_on_commit=False) as s:
        _seed_analyzed_clusters(s, n=5, age_hours=2.0)
        user = User(email="carol@test.com", interests="finance")
        s.add(user)
        s.commit()

    result = p_ai.select_stories(user, db_engine)
    scores = [p_ai.score_story(c, user) for c in result]
    assert scores == sorted(scores, reverse=True)


def test_select_48h_window(db_engine):
    p_ai = PersonalizationAgent()
    with Session(db_engine, expire_on_commit=False) as s:
        # 2 recent, 1 old
        _seed_analyzed_clusters(s, n=2, age_hours=5.0)
        old = StoryCluster(
            headline="Old story", categories="finance",
            status=StoryStatus.ANALYZED, article_count=1,
            first_seen=datetime.now(UTC) - timedelta(hours=60),
        )
        s.add(old)
        s.commit()

        user = User(email="dave@test.com", interests="finance")
        s.add(user)
        s.commit()

    result = p_ai.select_stories(user, db_engine)
    result_ids = {c.id for c in result}
    assert old.id not in result_ids


def test_select_empty_when_no_stories(db_engine):
    p_ai = PersonalizationAgent()
    with Session(db_engine, expire_on_commit=False) as s:
        user = User(email="eve@test.com", interests="finance")
        s.add(user)
        s.commit()

    result = p_ai.select_stories(user, db_engine)
    assert result == []


# --- T3.3: Briefing Generation ---

MOCK_BRIEFING_HTML = """\
<h2>Markets Rally on Fed Decision</h2>
<p>Stock markets rose 2.1% after the Fed held rates (Source: Reuters).</p>
<h2>Also Worth Watching</h2>
<p>EU passes new trade deal (Source: BBC).</p>"""


def _make_mock_writer():
    with patch.object(WriterAgent, "__init__", lambda self: None):
        agent = WriterAgent()
        agent.client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text=MOCK_BRIEFING_HTML)]
        agent.client.messages.create.return_value = mock_msg
        return agent


def test_briefing_contains_all_stories(db_engine):
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=3)
        user = User(email="test@test.com", interests="finance")
        s.add(user)
        s.commit()

    content = agent.generate_briefing(user, clusters, db_engine)
    assert isinstance(content, str)
    assert len(content) > 0


def test_briefing_has_source_attribution():
    """Mock Claude output should contain (Source: ...) patterns."""
    assert "(Source: Reuters)" in MOCK_BRIEFING_HTML
    assert "(Source: BBC)" in MOCK_BRIEFING_HTML


def test_briefing_respects_email_format(db_engine):
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=1)
        user = User(
            email="test@test.com", interests="finance",
            preferred_format=BriefingFormat.EMAIL,
        )
        s.add(user)
        s.commit()

    # Verify prompt includes format instruction
    agent.generate_briefing(user, clusters, db_engine)
    call_args = agent.client.messages.create.call_args
    prompt = call_args.kwargs["messages"][0]["content"]
    assert "email" in prompt.lower()


def test_briefing_handles_empty_stories(db_engine):
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        user = User(email="test@test.com", interests="finance")
        s.add(user)
        s.commit()

    result = agent.create_and_send(user, [], db_engine)
    assert result is None
    agent.client.messages.create.assert_not_called()


# --- T3.4: Email Delivery ---

def test_send_email_calls_resend(db_engine):
    agent = _make_mock_writer()
    user = User(email="test@test.com", interests="finance")

    with patch("prism.agents.w_ai.resend") as mock_resend:
        result = agent.send_email(user, "<h1>News</h1>")

    assert result is True
    mock_resend.Emails.send.assert_called_once()
    call_arg = mock_resend.Emails.send.call_args[0][0]
    assert call_arg["to"] == ["test@test.com"]
    assert "<h1>News</h1>" in call_arg["html"]


def test_send_email_subject_has_date(db_engine):
    agent = _make_mock_writer()
    user = User(email="test@test.com", interests="finance")

    with patch("prism.agents.w_ai.resend") as mock_resend:
        agent.send_email(user, "<p>content</p>")

    call_arg = mock_resend.Emails.send.call_args[0][0]
    today = datetime.now(UTC).strftime("%B %d, %Y")
    assert today in call_arg["subject"]


def test_send_email_failure_logged(caplog):
    agent = _make_mock_writer()
    user = User(email="test@test.com", interests="finance")

    with patch("prism.agents.w_ai.resend") as mock_resend:
        mock_resend.Emails.send.side_effect = Exception("API down")
        with caplog.at_level(logging.ERROR):
            result = agent.send_email(user, "<p>content</p>")

    assert result is False
    assert "Failed to send email" in caplog.text


def test_send_email_success_returns_true():
    agent = _make_mock_writer()
    user = User(email="test@test.com", interests="finance")

    with patch("prism.agents.w_ai.resend"):
        result = agent.send_email(user, "<p>content</p>")

    assert result is True


# --- T3.5: Briefing Storage and Tracking ---

def test_briefing_stored_in_db(db_engine):
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=2)
        user = User(email="store@test.com", interests="finance")
        s.add(user)
        s.commit()
        user_id = user.id

    with patch("prism.agents.w_ai.resend"):
        briefing = agent.create_and_send(user, clusters, db_engine)

    assert briefing is not None
    with Session(db_engine) as s:
        stored = s.get(Briefing, briefing.id)
        assert stored is not None
        assert stored.user_id == user_id
        assert stored.story_count == 2
        assert stored.content_html != ""


def test_briefing_marked_sent(db_engine):
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=1)
        user = User(email="sent@test.com", interests="finance")
        s.add(user)
        s.commit()

    with patch("prism.agents.w_ai.resend"):
        briefing = agent.create_and_send(user, clusters, db_engine)

    with Session(db_engine) as s:
        stored = s.get(Briefing, briefing.id)
        assert stored.sent is True
        assert stored.sent_at is not None


def test_briefing_not_marked_sent_on_failure(db_engine):
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=1)
        user = User(email="fail@test.com", interests="finance")
        s.add(user)
        s.commit()

    with patch("prism.agents.w_ai.resend") as mock_resend:
        mock_resend.Emails.send.side_effect = Exception("API down")
        briefing = agent.create_and_send(user, clusters, db_engine)

    with Session(db_engine) as s:
        stored = s.get(Briefing, briefing.id)
        assert stored.sent is False
        assert stored.sent_at is None


def test_briefing_skipped_no_stories(db_engine):
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        user = User(email="skip@test.com", interests="finance")
        s.add(user)
        s.commit()

    result = agent.create_and_send(user, [], db_engine)
    assert result is None

    with Session(db_engine) as s:
        count = len(s.exec(select(Briefing)).all())
        assert count == 0


# --- T8.7: Non-email format handling ---

def test_audio_script_stored_not_sent(db_engine, caplog):
    """Pro user with AUDIO_SCRIPT: stored but not delivered; skip is logged."""
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=1)
        user = User(
            email="audio@test.com", interests="finance",
            preferred_format=BriefingFormat.AUDIO_SCRIPT, is_pro=True,
        )
        s.add(user)
        s.commit()

    with caplog.at_level(logging.INFO):
        briefing = agent.create_and_send(user, clusters, db_engine)

    assert briefing is not None
    with Session(db_engine) as s:
        stored = s.get(Briefing, briefing.id)
        assert stored.sent is False
        assert stored.content_text != ""
        assert stored.content_html == ""
    assert "Skipping delivery" in caplog.text
    assert "audio_script" in caplog.text


def test_json_feed_stored_not_sent(db_engine, caplog):
    """Pro user with JSON_FEED: stored but not delivered; skip is logged."""
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=1)
        user = User(
            email="json@test.com", interests="finance",
            preferred_format=BriefingFormat.JSON_FEED, is_pro=True,
        )
        s.add(user)
        s.commit()

    with caplog.at_level(logging.INFO):
        briefing = agent.create_and_send(user, clusters, db_engine)

    assert briefing is not None
    with Session(db_engine) as s:
        stored = s.get(Briefing, briefing.id)
        assert stored.sent is False
    assert "JSON feed briefing" in caplog.text
    assert "API-only" in caplog.text


# --- T9.2: Tier enforcement in W_AI ---

def test_free_user_format_falls_back_to_email(db_engine, caplog):
    """Free user requesting AUDIO_SCRIPT gets email instead."""
    agent = _make_mock_writer()
    with Session(db_engine, expire_on_commit=False) as s:
        clusters = _seed_analyzed_clusters(s, n=1)
        user = User(
            email="freeaudio@test.com", interests="finance",
            preferred_format=BriefingFormat.AUDIO_SCRIPT, is_pro=False,
        )
        s.add(user)
        s.commit()

    with patch("prism.agents.w_ai.resend"):
        with caplog.at_level(logging.INFO):
            briefing = agent.create_and_send(user, clusters, db_engine)

    assert briefing is not None
    with Session(db_engine) as s:
        stored = s.get(Briefing, briefing.id)
        # Should be sent as email, not stored as text
        assert stored.content_html != ""
        assert stored.sent is True
    assert "falling back to email" in caplog.text
