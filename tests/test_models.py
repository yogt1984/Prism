"""Basic model tests to verify schema is correct."""

from prism.models import (
    BiasLabel,
    BriefingFormat,
    Category,
    Engagement,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    User,
)


def test_source_defaults():
    source = Source(name="Reuters", url="reuters.com")
    assert source.trust_score == 0.5
    assert source.bias_label == BiasLabel.UNKNOWN
    assert source.active is True


def test_story_cluster_lifecycle():
    cluster = StoryCluster()
    assert cluster.status == StoryStatus.RAW
    cluster.status = StoryStatus.ANALYZED
    assert cluster.status == StoryStatus.ANALYZED


def test_user_defaults():
    user = User(email="test@example.com")
    assert user.preferred_format == BriefingFormat.EMAIL
    assert user.briefing_depth == 10
    assert user.is_pro is False


def test_perspective_creation():
    p = Perspective(
        cluster_id=1,
        source_id=1,
        summary="Reuters frames this as a market correction",
        sentiment=-0.3,
        bias_label=BiasLabel.CENTER,
        key_claims='["S&P 500 dropped 2% (Source: Reuters)"]',
    )
    assert p.sentiment == -0.3
    assert p.bias_label == BiasLabel.CENTER


def test_engagement_tracking():
    e = Engagement(user_id=1, cluster_id=1, action="read", read_time_sec=45)
    assert e.action == "read"
    assert e.read_time_sec == 45


def test_categories_exist():
    assert Category.FINANCE == "finance"
    assert Category.POLITICS == "politics"
    assert Category.TECHNOLOGY == "technology"
    assert Category.SPORTS == "sports"
