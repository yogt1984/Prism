"""R_AI — Resonance Tracker Agent.

Scans analyzed story clusters for tracked keywords and computes
perception pressure over time. Runs after A_AI on the same schedule.
"""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.config import settings
from prism.metrics import perception_computed_total, timed_cycle
from prism.models import (
    Article,
    KeywordMention,
    KeywordTrack,
    PerceptionSnapshot,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
)
from prism.perception import (
    ClusterInput,
    PerceptionConfig,
    PerspectiveInput,
    compute_perception,
    compute_perception_momentum,
    scan_cluster_for_keyword,
)

logger = logging.getLogger(__name__)


class ResonanceTracker:
    """Scans analyzed clusters for tracked keywords and computes perception."""

    def _get_active_keywords(self, session: Session) -> list[KeywordTrack]:
        return list(
            session.exec(
                select(KeywordTrack).where(KeywordTrack.is_active == True)  # noqa: E712
            ).all()
        )

    def _get_recent_clusters(
        self, session: Session, window_hours: int,
    ) -> list[StoryCluster]:
        cutoff = datetime.now(UTC) - timedelta(hours=window_hours)
        return list(
            session.exec(
                select(StoryCluster)
                .where(StoryCluster.status == StoryStatus.ANALYZED)
                .where(StoryCluster.first_seen >= cutoff)
            ).all()
        )

    def _scan_and_record_mentions(
        self,
        session: Session,
        keyword: KeywordTrack,
        clusters: list[StoryCluster],
    ) -> list[int]:
        """Scan clusters for keyword mentions. Returns cluster IDs with hits."""
        aliases = [a.strip() for a in keyword.aliases.split(",") if a.strip()]
        matched_cluster_ids: list[int] = []

        for cluster in clusters:
            # Skip if we already recorded this keyword+cluster pair
            existing = session.exec(
                select(KeywordMention)
                .where(KeywordMention.keyword_id == keyword.id)
                .where(KeywordMention.cluster_id == cluster.id)
            ).first()
            if existing is not None:
                matched_cluster_ids.append(cluster.id)  # type: ignore[arg-type]
                continue

            # Load articles for scanning
            articles = session.exec(
                select(Article).where(Article.cluster_id == cluster.id)
            ).all()
            if not articles:
                continue

            # Build trust map
            source_ids = {a.source_id for a in articles}
            trust_map = {
                s.id: s.trust_score
                for s in session.exec(
                    select(Source).where(Source.id.in_(source_ids))  # type: ignore[union-attr]
                ).all()
            }

            result = scan_cluster_for_keyword(
                headline=cluster.headline,
                article_titles=[a.title for a in articles],
                source_ids=[a.source_id for a in articles],
                trust_map=trust_map,
                keyword=keyword.keyword,
                aliases=aliases,
                cluster_id=cluster.id,  # type: ignore[arg-type]
            )

            if result is not None:
                mention = KeywordMention(
                    keyword_id=keyword.id,
                    cluster_id=cluster.id,
                    mention_count=result.mention_count,
                    headline_hit=result.headline_hit,
                    source_count=result.source_count,
                    weighted_score=result.weighted_score,
                )
                session.add(mention)
                matched_cluster_ids.append(cluster.id)  # type: ignore[arg-type]

        return matched_cluster_ids

    def _compute_and_store_perception(
        self,
        session: Session,
        keyword: KeywordTrack,
        cluster_ids: list[int],
    ) -> None:
        """Compute perception for a keyword from its matching clusters."""
        if not cluster_ids:
            return

        now = datetime.now(UTC)
        config = PerceptionConfig(
            half_life_hours=float(settings.perception_half_life_hours),
        )

        # Build ClusterInput objects with perspectives
        cluster_inputs: list[ClusterInput] = []
        for cid in cluster_ids:
            cluster = session.get(StoryCluster, cid)
            if cluster is None:
                continue

            perspectives = session.exec(
                select(Perspective).where(Perspective.cluster_id == cid)
            ).all()

            # Get trust scores for perspective sources
            p_source_ids = {p.source_id for p in perspectives}
            trust_map = {
                s.id: s.trust_score
                for s in session.exec(
                    select(Source).where(Source.id.in_(p_source_ids))  # type: ignore[union-attr]
                ).all()
            } if p_source_ids else {}

            perspective_inputs = [
                PerspectiveInput(
                    source_id=p.source_id,
                    trust_score=trust_map.get(p.source_id, 0.5),
                    sentiment=p.sentiment,
                )
                for p in perspectives
            ]

            cluster_inputs.append(ClusterInput(
                cluster_id=cid,
                source_count=cluster.article_count,
                first_seen=cluster.first_seen,
                perspectives=perspective_inputs,
            ))

        result = compute_perception(cluster_inputs, now, config)

        # Get previous snapshot for momentum
        previous = session.exec(
            select(PerceptionSnapshot)
            .where(PerceptionSnapshot.keyword_id == keyword.id)
            .order_by(PerceptionSnapshot.computed_at.desc())  # type: ignore[union-attr]
        ).first()

        previous_perception = previous.perception if previous else 0.0
        momentum = compute_perception_momentum(result.perception, previous_perception)

        snapshot = PerceptionSnapshot(
            keyword_id=keyword.id,
            perception=result.perception,
            salience=result.salience,
            valence=result.valence,
            momentum=momentum,
            cluster_count=result.cluster_count,
            source_count=result.source_count,
        )
        session.add(snapshot)
        perception_computed_total.inc()

        logger.info(
            "Perception for '%s': P=%.3f (salience=%.3f, valence=%.3f, momentum=%+.3f, %d clusters)",
            keyword.keyword,
            result.perception,
            result.salience,
            result.valence,
            momentum,
            result.cluster_count,
        )

    @timed_cycle("perception")
    def process_keywords(self, engine: Engine | None = None) -> None:
        """Scan all tracked keywords against recent clusters."""
        from prism.db import get_engine

        e = engine or get_engine()
        with Session(e) as session:
            keywords = self._get_active_keywords(session)
            if not keywords:
                logger.debug("No active keywords to track")
                return

            clusters = self._get_recent_clusters(
                session, settings.perception_window_hours,
            )
            if not clusters:
                logger.debug("No recent analyzed clusters")
                return

            logger.info(
                "Scanning %d keywords against %d clusters",
                len(keywords), len(clusters),
            )

            for keyword in keywords:
                try:
                    matched_ids = self._scan_and_record_mentions(
                        session, keyword, clusters,
                    )
                    self._compute_and_store_perception(
                        session, keyword, matched_ids,
                    )
                except Exception:
                    logger.exception(
                        "Perception computation failed for keyword '%s'",
                        keyword.keyword,
                    )

            session.commit()
