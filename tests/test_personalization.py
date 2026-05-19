"""Tests for P_AI personalization scoring."""

from datetime import UTC, datetime, timedelta

from prism.agents.p_ai import PersonalizationAgent
from prism.models import StoryCluster, StoryStatus, User


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
