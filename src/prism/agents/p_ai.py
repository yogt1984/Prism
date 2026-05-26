"""P_AI — Personalization Agent.

Manages user profiles, ranks stories by relevance,
and selects stories for each user's briefing.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.config import settings
from prism.db import get_engine
from prism.models import (
    Engagement,
    StoryCluster,
    StoryStatus,
    User,
)

logger = logging.getLogger(__name__)


class PersonalizationAgent:
    def __init__(self) -> None:
        pass

    # Engagement action weights for personalization scoring
    _ACTION_WEIGHTS: dict[str, float] = {
        "save": 2.0,
        "read": 1.0,
        "open": 0.5,
        "skip": -1.0,
    }

    def _compute_engagement_weights(
        self, user_id: int, engine: Engine | None = None,
    ) -> dict[str, float]:
        """Compute per-category affinity from recent engagement history.

        Returns a dict mapping category names to normalized [0.0, 1.0] scores.
        """
        e = engine or get_engine()
        cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=30)

        with Session(e) as session:
            engagements = session.exec(
                select(Engagement).where(
                    Engagement.user_id == user_id,
                    Engagement.created_at >= cutoff,
                )
            ).all()

            if not engagements:
                return {}

            # Accumulate raw scores per category
            raw: dict[str, float] = {}
            for eng in engagements:
                cluster = session.get(StoryCluster, eng.cluster_id)
                if cluster is None or not cluster.categories:
                    continue

                action = eng.action.lower()
                weight = self._ACTION_WEIGHTS.get(action, 0.0)
                # For "read" action, only count if read_time > 30s
                if action == "read" and eng.read_time_sec <= 30:
                    weight = 0.5  # treat short reads as "open"

                for cat in cluster.categories.split(","):
                    cat = cat.strip()
                    if cat:
                        raw[cat] = raw.get(cat, 0.0) + weight

        if not raw:
            return {}

        # Normalize to 0.0–1.0 range
        min_val = min(raw.values())
        max_val = max(raw.values())
        if max_val == min_val:
            # All categories have the same score
            return {cat: 1.0 if v > 0 else 0.0 for cat, v in raw.items()}

        return {
            cat: max(0.0, min(1.0, (v - min_val) / (max_val - min_val)))
            for cat, v in raw.items()
        }

    def score_story(
        self, cluster: StoryCluster, user: User,
        engagement_weights: dict[str, float] | None = None,
    ) -> float:
        """Score a story's relevance to a user. Higher = more relevant."""
        score = 0.0

        # Interest match: does the story's category overlap with user interests?
        user_interests = set(user.interests.split(",")) if user.interests else set()
        story_categories = set(cluster.categories.split(",")) if cluster.categories else set()
        overlap = user_interests & story_categories
        if overlap:
            score += 5.0 * len(overlap)

        # Recency bonus: newer stories score higher
        first_seen = cluster.first_seen
        if first_seen.tzinfo is None:
            first_seen = first_seen.replace(tzinfo=UTC)
        age_hours = (datetime.now(UTC) - first_seen).total_seconds() / 3600
        if age_hours < 6:
            score += 3.0
        elif age_hours < 24:
            score += 1.5

        # Source diversity: stories with more perspectives are more valuable
        score += min(cluster.article_count * 0.5, 3.0)

        # Engagement-based bonus
        if engagement_weights:
            engagement_bonus = 0.0
            for cat in story_categories:
                cat = cat.strip()
                engagement_bonus += engagement_weights.get(cat, 0.0) * 3.0
            score += engagement_bonus

        return score

    def select_stories(
        self, user: User, engine: Engine | None = None,
    ) -> list[StoryCluster]:
        """Select and rank stories for a user's briefing."""
        e = engine or get_engine()
        with Session(e) as session:
            # Get analyzed stories from the last 48 hours
            # Use naive UTC for SQLite text comparison compatibility
            cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=48)
            clusters = session.exec(
                select(StoryCluster).where(
                    StoryCluster.status == StoryStatus.ANALYZED,
                    StoryCluster.first_seen >= cutoff,
                )
            ).all()

            # Get stories the user has already seen
            seen_ids = set()
            user_engagements = session.exec(
                select(Engagement).where(Engagement.user_id == user.id)
            ).all()
            for eng in user_engagements:
                seen_ids.add(eng.cluster_id)

            # Score, filter seen, sort
            candidates = [c for c in clusters if c.id not in seen_ids]

            # Tier enforcement: free users limited to first interest category
            if not user.is_pro and user.interests:
                allowed_cat = user.interests.split(",")[0].strip()
                candidates = [
                    c for c in candidates
                    if allowed_cat in (c.categories or "").split(",")
                ]

            # Compute engagement weights once for this user
            eng_weights = self._compute_engagement_weights(user.id, engine=e)
            if eng_weights:
                logger.info("Engagement weights for %s: %s", user.email, eng_weights)

            scored = [(self.score_story(c, user, eng_weights or None), c) for c in candidates]
            scored.sort(key=lambda x: x[0], reverse=True)

            limit = user.briefing_depth or settings.default_briefing_stories
            if not user.is_pro:
                limit = min(limit, settings.default_briefing_stories)
            else:
                limit = min(limit, settings.max_briefing_stories)
            selected = [cluster for _, cluster in scored[:limit]]

            logger.info("Selected %d stories for user %s (from %d candidates)",
                        len(selected), user.email, len(candidates))
            return selected

    def record_engagement(
        self, user_id: int, cluster_id: int, action: str,
        read_time_sec: int = 0, engine: Engine | None = None,
    ) -> None:
        """Record a user engagement event for future personalization."""
        e = engine or get_engine()
        with Session(e) as session:
            engagement = Engagement(
                user_id=user_id,
                cluster_id=cluster_id,
                action=action,
                read_time_sec=read_time_sec,
            )
            session.add(engagement)
            session.commit()

    def get_all_users(self, engine: Engine | None = None) -> list[User]:
        """Get all active users."""
        e = engine or get_engine()
        with Session(e) as session:
            return list(session.exec(select(User)).all())
