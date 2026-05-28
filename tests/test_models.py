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
    TopicResonance,
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


def test_story_cluster_resonance_default():
    cluster = StoryCluster()
    assert cluster.resonance_score == 0.0


def test_topic_resonance_roundtrip(tmp_path):
    """Create a TopicResonance row, persist it, and read it back."""
    from sqlmodel import Session, SQLModel, create_engine

    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)

    # Need a source and cluster for FK constraints
    with Session(engine) as session:
        source = Source(name="Reuters", url="https://reuters.com")
        session.add(source)
        session.flush()
        cluster = StoryCluster(headline="Test", article_count=3)
        session.add(cluster)
        session.flush()

        tr = TopicResonance(
            cluster_id=cluster.id,
            resonance=12.5,
            momentum=3.2,
            peak_resonance=15.0,
            mention_count=8,
            source_count=4,
            authority_weighted_sum=6.1,
            breadth=2.32,
            window_hours=72,
        )
        session.add(tr)
        session.commit()

        loaded = session.get(TopicResonance, tr.id)
        assert loaded is not None
        assert loaded.resonance == 12.5
        assert loaded.momentum == 3.2
        assert loaded.peak_resonance == 15.0
        assert loaded.mention_count == 8
        assert loaded.source_count == 4
        assert loaded.authority_weighted_sum == 6.1
        assert loaded.breadth == 2.32
        assert loaded.window_hours == 72
        assert loaded.computed_at is not None
