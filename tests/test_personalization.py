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


# --- T9.2: Tier enforcement in P_AI ---

def _seed_multi_category(session: Session) -> list[StoryCluster]:
    """Create clusters across several categories."""
    clusters = []
    for i, cat in enumerate(["finance", "sports", "technology", "politics"]):
        c = StoryCluster(
            headline=f"{cat} story {i}",
            categories=cat,
            status=StoryStatus.ANALYZED,
            article_count=2,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        session.add(c)
        clusters.append(c)
    session.commit()
    for c in clusters:
        session.refresh(c)
    return clusters


def test_free_user_limited_to_first_interest(db_engine):
    """Free users only see stories matching their first interest category."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        _seed_multi_category(s)
        user = User(
            id=1, email="free@test.com",
            interests="finance,sports", is_pro=False,
        )
        s.add(user)
        s.commit()

    detached = User(id=1, email="free@test.com", interests="finance,sports", is_pro=False)
    stories = p_ai.select_stories(detached, engine=db_engine)
    cats = {c.categories for c in stories}
    assert cats == {"finance"}, f"Free user should only get first interest, got {cats}"


def test_pro_user_gets_all_interests(db_engine):
    """Pro users see stories from all their interest categories."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        _seed_multi_category(s)
        user = User(
            id=1, email="pro@test.com",
            interests="finance,sports", is_pro=True,
        )
        s.add(user)
        s.commit()

    detached = User(id=1, email="pro@test.com", interests="finance,sports", is_pro=True)
    stories = p_ai.select_stories(detached, engine=db_engine)
    cats = {c.categories for c in stories}
    assert "finance" in cats
    assert "sports" in cats


def test_free_user_capped_at_default_stories(db_engine):
    """Free users capped at default_briefing_stories even if briefing_depth is higher."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        # Create 15 finance clusters
        for i in range(15):
            s.add(StoryCluster(
                headline=f"Finance story {i}", categories="finance",
                status=StoryStatus.ANALYZED, article_count=2,
                first_seen=datetime.now(UTC) - timedelta(hours=1),
            ))
        s.commit()

    detached = User(
        id=1, email="free@test.com", interests="finance",
        is_pro=False, briefing_depth=25,
    )
    stories = p_ai.select_stories(detached, engine=db_engine)
    # default_briefing_stories = 10
    assert len(stories) <= 10


def test_pro_user_gets_up_to_max_stories(db_engine):
    """Pro users can get up to max_briefing_stories."""
    p_ai = PersonalizationAgent()
    with Session(db_engine) as s:
        for i in range(30):
            s.add(StoryCluster(
                headline=f"Story {i}", categories="finance",
                status=StoryStatus.ANALYZED, article_count=2,
                first_seen=datetime.now(UTC) - timedelta(hours=1),
            ))
        s.commit()

    detached = User(
        id=1, email="pro@test.com", interests="finance",
        is_pro=True, briefing_depth=30,
    )
    stories = p_ai.select_stories(detached, engine=db_engine)
    # max_briefing_stories = 25
    assert len(stories) <= 25


# --- T12.1: Engagement weight calculation ---


def _seed_engagement_data(session: Session, user_id: int, cluster_id: int,
                          action: str, read_time_sec: int = 0,
                          age_days: int = 0) -> None:
    """Create an engagement with a specific age."""
    eng = Engagement(
        user_id=user_id,
        cluster_id=cluster_id,
        action=action,
        read_time_sec=read_time_sec,
        created_at=datetime.now(UTC) - timedelta(days=age_days),
    )
    session.add(eng)


def _make_cluster(session: Session, categories: str) -> int:
    """Create a cluster with given categories, return its id."""
    c = StoryCluster(
        headline=f"Story about {categories}",
        categories=categories,
        status=StoryStatus.ANALYZED,
        article_count=2,
        first_seen=datetime.now(UTC) - timedelta(hours=1),
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c.id


class TestEngagementWeights:
    """T12.1: _compute_engagement_weights tests."""

    def test_empty_history_returns_empty(self, db_engine):
        """No engagements → empty dict."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="empty@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

        result = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert result == {}

    def test_saves_produce_high_weight(self, db_engine):
        """Multiple saves on finance → high finance weight."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="saver@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "finance")
            for _ in range(5):
                _seed_engagement_data(s, uid, cid, "save")
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert "finance" in weights
        assert weights["finance"] > 0.5

    def test_skips_produce_low_weight(self, db_engine):
        """All skips on sports → low/zero sports weight."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="skipper@t.com", interests="sports")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "sports")
            for _ in range(5):
                _seed_engagement_data(s, uid, cid, "skip")
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert "sports" in weights
        assert weights["sports"] == 0.0

    def test_saves_outweigh_skips(self, db_engine):
        """Category with saves should score higher than category with skips."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="mixed@t.com", interests="finance,sports")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            fin_id = _make_cluster(s, "finance")
            sport_id = _make_cluster(s, "sports")

            for _ in range(3):
                _seed_engagement_data(s, uid, fin_id, "save")
            for _ in range(3):
                _seed_engagement_data(s, uid, sport_id, "skip")
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert weights["finance"] > weights["sports"]

    def test_read_over_30s_counts_as_read(self, db_engine):
        """Read with >30s read_time gets full read weight (1.0)."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="reader@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "finance")
            _seed_engagement_data(s, uid, cid, "read", read_time_sec=60)
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert "finance" in weights
        assert weights["finance"] > 0.0

    def test_short_read_treated_as_open(self, db_engine):
        """Read with <=30s read_time gets open weight (0.5) instead of read (1.0)."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="short@t.com", interests="finance,sports")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            fin_id = _make_cluster(s, "finance")
            sport_id = _make_cluster(s, "sports")

            # Short read on finance (0.5 weight)
            _seed_engagement_data(s, uid, fin_id, "read", read_time_sec=10)
            # Long read on sports (1.0 weight)
            _seed_engagement_data(s, uid, sport_id, "read", read_time_sec=60)
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert weights["sports"] > weights["finance"]

    def test_old_engagements_excluded(self, db_engine):
        """Engagements older than 30 days are not counted."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="old@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "finance")
            _seed_engagement_data(s, uid, cid, "save", age_days=31)
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert weights == {}

    def test_recent_engagements_included(self, db_engine):
        """Engagements within 30 days are counted."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="recent@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "finance")
            _seed_engagement_data(s, uid, cid, "save", age_days=15)
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert "finance" in weights
        assert weights["finance"] > 0.0

    def test_normalized_range(self, db_engine):
        """All weights must be in [0.0, 1.0]."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="norm@t.com", interests="finance,sports,technology")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            fin_id = _make_cluster(s, "finance")
            sport_id = _make_cluster(s, "sports")
            tech_id = _make_cluster(s, "technology")

            for _ in range(5):
                _seed_engagement_data(s, uid, fin_id, "save")
            for _ in range(3):
                _seed_engagement_data(s, uid, sport_id, "open")
            for _ in range(4):
                _seed_engagement_data(s, uid, tech_id, "skip")
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        for cat, val in weights.items():
            assert 0.0 <= val <= 1.0, f"{cat} weight {val} out of range"

    def test_multi_category_cluster(self, db_engine):
        """Engagement on a multi-category cluster boosts all its categories."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="multi@t.com", interests="finance,technology")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "finance,technology")
            _seed_engagement_data(s, uid, cid, "save")
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert "finance" in weights
        assert "technology" in weights

    def test_single_category_all_same_action(self, db_engine):
        """Single category with uniform positive action → weight 1.0."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="uniform@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "finance")
            for _ in range(3):
                _seed_engagement_data(s, uid, cid, "save")
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        # Only one category with positive score → normalized to 1.0
        assert weights["finance"] == 1.0

    def test_open_weight(self, db_engine):
        """Open action contributes positive weight."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="opener@t.com", interests="finance")
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            cid = _make_cluster(s, "finance")
            _seed_engagement_data(s, uid, cid, "open")
            s.commit()

        weights = p_ai._compute_engagement_weights(uid, engine=db_engine)
        assert weights["finance"] > 0.0


# --- T12.2: Engagement weights integrated into scoring ---


class TestEngagementScoring:
    """T12.2: Verify engagement weights affect score_story and select_stories."""

    def test_engagement_weight_boosts_score(self):
        """Story in high-weight category scores higher than without weights."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        cluster = StoryCluster(
            categories="finance",
            status=StoryStatus.ANALYZED,
            article_count=2,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        score_without = p_ai.score_story(cluster, user)
        score_with = p_ai.score_story(cluster, user, engagement_weights={"finance": 1.0})
        assert score_with > score_without

    def test_engagement_bonus_is_3_per_category(self):
        """Engagement bonus = weight * 3.0 per matching category."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        cluster = StoryCluster(
            categories="finance",
            status=StoryStatus.ANALYZED,
            article_count=2,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        base = p_ai.score_story(cluster, user)
        boosted = p_ai.score_story(cluster, user, engagement_weights={"finance": 0.5})
        assert abs((boosted - base) - 1.5) < 0.01  # 0.5 * 3.0 = 1.5

    def test_no_weights_identical_to_none(self):
        """Passing None or empty dict produces the same score as no weights."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        cluster = StoryCluster(
            categories="finance",
            status=StoryStatus.ANALYZED,
            article_count=2,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        base = p_ai.score_story(cluster, user)
        with_none = p_ai.score_story(cluster, user, engagement_weights=None)
        with_empty = p_ai.score_story(cluster, user, engagement_weights={})
        assert base == with_none
        assert base == with_empty

    def test_unrelated_weight_no_effect(self):
        """Weight for a category not in the story has no effect."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        cluster = StoryCluster(
            categories="finance",
            status=StoryStatus.ANALYZED,
            article_count=2,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        base = p_ai.score_story(cluster, user)
        with_other = p_ai.score_story(cluster, user, engagement_weights={"sports": 1.0})
        assert base == with_other

    def test_multi_category_gets_multi_bonus(self):
        """Story with two matching categories gets bonus for both."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance,technology")
        cluster = StoryCluster(
            categories="finance,technology",
            status=StoryStatus.ANALYZED,
            article_count=2,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        base = p_ai.score_story(cluster, user)
        weights = {"finance": 1.0, "technology": 0.5}
        boosted = p_ai.score_story(cluster, user, engagement_weights=weights)
        expected_bonus = 1.0 * 3.0 + 0.5 * 3.0  # 4.5
        assert abs((boosted - base) - expected_bonus) < 0.01

    def test_interest_still_dominates(self):
        """Interest match (+5.0) still contributes more than engagement (+3.0 max)."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        # Story matching interest
        matching = StoryCluster(
            categories="finance",
            status=StoryStatus.ANALYZED,
            article_count=1,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        # Story not matching interest but with high engagement weight
        non_matching = StoryCluster(
            categories="sports",
            status=StoryStatus.ANALYZED,
            article_count=1,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        weights = {"sports": 1.0}
        score_match = p_ai.score_story(matching, user, engagement_weights=weights)
        score_engage = p_ai.score_story(non_matching, user, engagement_weights=weights)
        assert score_match > score_engage

    def test_engagement_changes_sort_order(self, db_engine):
        """Engagement weights can reorder stories with equal base scores."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="order@t.com", interests="finance,sports", is_pro=True)
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            # Old clusters for engagement history (already seen → excluded)
            old_sport_id = _make_cluster(s, "sports")
            for _ in range(5):
                _seed_engagement_data(s, uid, old_sport_id, "save")
            s.commit()

            # New unseen clusters that will be scored
            fin_id = _make_cluster(s, "finance")
            sport_id = _make_cluster(s, "sports")

        detached = User(id=uid, email="order@t.com", interests="finance,sports", is_pro=True)
        stories = p_ai.select_stories(detached, engine=db_engine)

        # Sports should come before finance due to engagement weights
        sport_idx = next((i for i, c in enumerate(stories) if c.id == sport_id), None)
        fin_idx = next((i for i, c in enumerate(stories) if c.id == fin_id), None)
        assert sport_idx is not None and fin_idx is not None
        assert sport_idx < fin_idx

    def test_select_stories_without_engagement_unchanged(self, db_engine):
        """select_stories with no engagement history gives same result as before."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="noeng@t.com", interests="finance", is_pro=True)
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id
            _make_cluster(s, "finance")

        detached = User(id=uid, email="noeng@t.com", interests="finance", is_pro=True)
        stories = p_ai.select_stories(detached, engine=db_engine)
        assert len(stories) == 1  # the single finance cluster

    def test_select_stories_calls_weights_once(self, db_engine):
        """Engagement weights are computed once, not per-story."""
        from unittest.mock import patch
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="once@t.com", interests="finance", is_pro=True)
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id
            for i in range(3):
                _make_cluster(s, "finance")

        detached = User(id=uid, email="once@t.com", interests="finance", is_pro=True)
        with patch.object(p_ai, "_compute_engagement_weights", wraps=p_ai._compute_engagement_weights) as mock:
            p_ai.select_stories(detached, engine=db_engine)
            assert mock.call_count == 1


# --- T-RES.8: Resonance integrated into ranking ---


class TestResonanceRanking:
    """T-RES.8: Verify resonance_score affects story ranking in P_AI."""

    def test_equal_interest_higher_resonance_wins(self):
        """Between two stories with equal interest match, higher resonance ranks first."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        low_res = StoryCluster(
            categories="finance", status=StoryStatus.ANALYZED,
            article_count=2, resonance_score=1.0,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        high_res = StoryCluster(
            categories="finance", status=StoryStatus.ANALYZED,
            article_count=2, resonance_score=20.0,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        assert p_ai.score_story(high_res, user) > p_ai.score_story(low_res, user)

    def test_interest_dominates_resonance(self):
        """A low-interest high-resonance story does not outrank a high-interest low-resonance story."""
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        matching = StoryCluster(
            categories="finance", status=StoryStatus.ANALYZED,
            article_count=1, resonance_score=1.0,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        non_matching = StoryCluster(
            categories="sports", status=StoryStatus.ANALYZED,
            article_count=1, resonance_score=10.0,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        assert p_ai.score_story(matching, user) > p_ai.score_story(non_matching, user)

    def test_zero_weight_disables_boost(self):
        """resonance_ranking_weight = 0.0 disables the boost entirely."""
        from unittest.mock import patch
        p_ai = PersonalizationAgent()
        user = User(email="t@t.com", interests="finance")
        cluster = StoryCluster(
            categories="finance", status=StoryStatus.ANALYZED,
            article_count=2, resonance_score=100.0,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        with patch("prism.agents.p_ai.settings") as mock_settings:
            mock_settings.resonance_ranking_weight = 0.0
            mock_settings.default_briefing_stories = 10
            mock_settings.max_briefing_stories = 25
            score_disabled = p_ai.score_story(cluster, user)

        cluster_no_res = StoryCluster(
            categories="finance", status=StoryStatus.ANALYZED,
            article_count=2, resonance_score=0.0,
            first_seen=datetime.now(UTC) - timedelta(hours=1),
        )
        with patch("prism.agents.p_ai.settings") as mock_settings:
            mock_settings.resonance_ranking_weight = 0.0
            mock_settings.default_briefing_stories = 10
            mock_settings.max_briefing_stories = 25
            score_no_res = p_ai.score_story(cluster_no_res, user)

        assert score_disabled == score_no_res

    def test_resonance_changes_ranking_order(self, db_engine):
        """Resonance score can reorder stories with equal interest/recency."""
        p_ai = PersonalizationAgent()
        with Session(db_engine) as s:
            user = User(email="rank@t.com", interests="finance", is_pro=True)
            s.add(user)
            s.commit()
            s.refresh(user)
            uid = user.id

            c1 = StoryCluster(
                headline="Low resonance",
                categories="finance", status=StoryStatus.ANALYZED,
                article_count=2, resonance_score=0.5,
                first_seen=datetime.now(UTC) - timedelta(hours=1),
            )
            c2 = StoryCluster(
                headline="High resonance",
                categories="finance", status=StoryStatus.ANALYZED,
                article_count=2, resonance_score=50.0,
                first_seen=datetime.now(UTC) - timedelta(hours=1),
            )
            s.add(c1)
            s.add(c2)
            s.commit()
            s.refresh(c1)
            s.refresh(c2)
            c1_id, c2_id = c1.id, c2.id

        detached = User(id=uid, email="rank@t.com", interests="finance", is_pro=True)
        stories = p_ai.select_stories(detached, engine=db_engine)
        ids = [c.id for c in stories]
        assert ids.index(c2_id) < ids.index(c1_id)
