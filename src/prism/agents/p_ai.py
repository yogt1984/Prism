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

    def score_story(self, cluster: StoryCluster, user: User) -> float:
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
            engagements = session.exec(
                select(Engagement).where(Engagement.user_id == user.id)
            ).all()
            for e in engagements:
                seen_ids.add(e.cluster_id)

            # Score, filter seen, sort
            candidates = [c for c in clusters if c.id not in seen_ids]
            scored = [(self.score_story(c, user), c) for c in candidates]
            scored.sort(key=lambda x: x[0], reverse=True)

            limit = user.briefing_depth or settings.default_briefing_stories
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
