"""Tests for P_AI personalization scoring and engagement recording."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from sqlmodel import Session, select

from prism.agents.p_ai import PersonalizationAgent
from prism.db import init_db
from prism.models import Engagement, StoryCluster, StoryStatus, User


def test_score_interest_match():
    p_ai = PersonalizationAgent()
    user = User(email="t@t.com", interests="finance,technology")
    cluster = StoryCluster(
        categories="finance",
        status=StoryStatus.ANALYZED,
        article_count=3,
        first_seen=datetime.now(UTC) - timedelta(hours=1),
    )
    score = p_ai.score_story(cluster, user)
    # Interest match (5.0) + recency <6h (3.0) + diversity 3*0.5 (1.5)
    assert score == 9.5


def test_score_no_interest_match():
    p_ai = PersonalizationAgent()
    user = User(email="t@t.com", interests="sports")
    cluster = StoryCluster(
        categories="finance",
        status=StoryStatus.ANALYZED,
        article_count=1,
        first_seen=datetime.now(UTC) - timedelta(hours=30),
    )
    score = p_ai.score_story(cluster, user)
    # No interest match (0) + recency >24h (0) + diversity 1*0.5 (0.5)
    assert score == 0.5


def test_score_recency_tiers():
    p_ai = PersonalizationAgent()
    user = User(email="t@t.com", interests="")

    fresh = StoryCluster(categories="", article_count=1,
                         first_seen=datetime.now(UTC) - timedelta(hours=2))
    medium = StoryCluster(categories="", article_count=1,
                          first_seen=datetime.now(UTC) - timedelta(hours=12))
    old = StoryCluster(categories="", article_count=1,
                       first_seen=datetime.now(UTC) - timedelta(hours=30))

    assert p_ai.score_story(fresh, user) > p_ai.score_story(medium, user)
    assert p_ai.score_story(medium, user) > p_ai.score_story(old, user)


# --- T8.5: Engagement recording ---

@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


def _seed_user_and_cluster(session: Session) -> tuple[int, int, User]:
    """Create a user and cluster, return (user_id, cluster_id, detached user)."""
    user = User(email="test@test.com", interests="finance")
    session.add(user)
    session.commit()
    session.refresh(user)

    cluster = StoryCluster(
        headline="Test story", categories="finance",
        status=StoryStatus.ANALYZED, article_count=2,
        first_seen=datetime.now(UTC) - timedelta(hours=1),
    )
    session.add(cluster)
    session.commit()
    session.refresh(cluster)

    uid, cid = user.id, cluster.id
    # Build a detached User with id pre-loaded for select_stories
    detached_user = User(id=uid, email=user.email, interests=user.interests)
    return uid, cid, detached_user


def test_record_engagement_creates_row(db_engine):
    """record_engagement persists an Engagement row."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        uid, cid, _ = _seed_user_and_cluster(s)

    p_ai.record_engagement(uid, cid, "open", engine=db_engine)

    with Session(db_engine) as s:
        rows = s.exec(select(Engagement)).all()
        assert len(rows) == 1
        assert rows[0].user_id == uid
        assert rows[0].cluster_id == cid


def test_record_engagement_stores_action(db_engine):
    """The action field is preserved for each engagement type."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        uid, cid, _ = _seed_user_and_cluster(s)

    for action in ("open", "read", "save", "skip"):
        p_ai.record_engagement(uid, cid, action, engine=db_engine)

    with Session(db_engine) as s:
        actions = {e.action for e in s.exec(select(Engagement)).all()}
        assert actions == {"open", "read", "save", "skip"}


def test_record_engagement_stores_read_time(db_engine):
    """read_time_sec persists correctly."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        uid, cid, _ = _seed_user_and_cluster(s)

    p_ai.record_engagement(uid, cid, "read", read_time_sec=45, engine=db_engine)

    with Session(db_engine) as s:
        eng = s.exec(select(Engagement)).one()
        assert eng.read_time_sec == 45


def test_record_engagement_excludes_from_selection(db_engine):
    """Stories with recorded engagement are excluded from select_stories."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        uid, cid, user = _seed_user_and_cluster(s)

    # Before engagement, story is selected
    stories_before = p_ai.select_stories(user, engine=db_engine)
    assert any(c.id == cid for c in stories_before)

    # Record engagement
    p_ai.record_engagement(uid, cid, "read", engine=db_engine)

    # After engagement, story is excluded
    stories_after = p_ai.select_stories(user, engine=db_engine)
    assert all(c.id != cid for c in stories_after)
