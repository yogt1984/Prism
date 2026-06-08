"""Source lifecycle management — probation promotion and evaluation."""

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.config import settings
from prism.models import Article, BiasLabel, Perspective, Source, SourceStatus, StoryCluster

logger = logging.getLogger(__name__)


def promote_to_probation(engine: Engine) -> int:
    """Promote candidates with sufficient sightings to probation.

    Criteria: sighting_count >= 3 AND status == "candidate"

    Returns count of promoted sources.
    """
    promoted = 0
    with Session(engine) as session:
        candidates = session.exec(
            select(Source).where(
                Source.status == SourceStatus.CANDIDATE,
                Source.sighting_count >= 3,
            )
        ).all()

        for source in candidates:
            source.status = SourceStatus.PROBATION
            source.trust_score = 0.1
            source.active = True
            source.probation_start = datetime.now(UTC)
            promoted += 1
            logger.info(
                "Source '%s' (%s) promoted to probation",
                source.name, source.url,
            )

        session.commit()

    if promoted:
        logger.info("Promoted %d candidates to probation", promoted)
    return promoted


def cross_validate_cluster(cluster_id: int, engine: Engine) -> None:
    """Score probation source articles in a cluster against trusted sources.

    For each article from a probation source in this cluster:
    - If the cluster also contains an article from a trusted/seed source
      → increment articles_validated
    - If the cluster contains ONLY probation articles (no trusted corroboration)
      AND the cluster has few articles (<=2)
      → increment articles_failed
    """
    with Session(engine) as session:
        articles = session.exec(
            select(Article, Source).join(Source, Article.source_id == Source.id).where(
                Article.cluster_id == cluster_id
            )
        ).all()

        if not articles:
            return

        trusted_present = any(
            source.status in (SourceStatus.SEED, SourceStatus.TRUSTED)
            for _, source in articles
        )

        probation_sources: dict[int, Source] = {}
        for article, source in articles:
            if source.status == SourceStatus.PROBATION:
                probation_sources[source.id] = source

        if not probation_sources:
            return  # no probation sources in this cluster

        for source_id, source in probation_sources.items():
            if trusted_present:
                source.articles_validated += 1
            else:
                # Only count as failure if cluster has few articles
                # (single-source clusters are suspicious)
                cluster = session.get(StoryCluster, cluster_id)
                if cluster and cluster.article_count <= 2:
                    source.articles_failed += 1
                # else: multi-source cluster without trusted sources is ambiguous, skip

            # Update trust score during probation
            total = source.articles_validated + source.articles_failed
            source.trust_score = 0.1 + (source.articles_validated / max(total, 1)) * 0.4

        session.commit()


def _infer_bias_label(source: Source, session: Session) -> None:
    """Infer initial bias label from perspective sentiment data.

    Maps average sentiment to a bias label:
      < -0.3 → left
      -0.3 to -0.1 → center_left
      -0.1 to 0.1 → center
      0.1 to 0.3 → center_right
      > 0.3 → right
    """
    perspectives = session.exec(
        select(Perspective).join(
            Article, Perspective.cluster_id == Article.cluster_id
        ).where(Article.source_id == source.id)
    ).all()

    if not perspectives:
        source.bias_label = BiasLabel.UNKNOWN
        return

    avg_sentiment = sum(p.sentiment for p in perspectives) / len(perspectives)

    if avg_sentiment < -0.3:
        source.bias_label = BiasLabel.LEFT
    elif avg_sentiment < -0.1:
        source.bias_label = BiasLabel.CENTER_LEFT
    elif avg_sentiment <= 0.1:
        source.bias_label = BiasLabel.CENTER
    elif avg_sentiment <= 0.3:
        source.bias_label = BiasLabel.CENTER_RIGHT
    else:
        source.bias_label = BiasLabel.RIGHT

    logger.info(
        "Source '%s' bias inferred: %s (avg_sentiment=%.3f, n=%d)",
        source.name, source.bias_label.value, avg_sentiment, len(perspectives),
    )


def evaluate_probation_sources(engine: Engine) -> dict[str, int]:
    """Evaluate all probation sources past their probation window.

    Returns {"promoted": N, "rejected": N, "reset": N}.
    """
    now = datetime.now(UTC)
    probation_days = settings.source_probation_days
    min_articles = settings.source_promotion_min_articles
    min_ratio = settings.source_promotion_min_ratio
    results = {"promoted": 0, "rejected": 0, "reset": 0}

    with Session(engine) as session:
        sources = session.exec(
            select(Source).where(
                Source.status == SourceStatus.PROBATION,
                Source.probation_start != None,  # noqa: E711
                Source.probation_start <= now - timedelta(days=probation_days),
            )
        ).all()

        for source in sources:
            total = source.articles_validated + source.articles_failed
            ratio = source.articles_validated / max(total, 1)

            source.last_evaluated = now

            if source.articles_validated >= min_articles and ratio >= min_ratio:
                # Promote
                source.status = SourceStatus.TRUSTED
                source.trust_score = 0.5
                _infer_bias_label(source, session)
                results["promoted"] += 1
                logger.info(
                    "Source '%s' promoted to trusted (validated=%d, ratio=%.2f)",
                    source.name, source.articles_validated, ratio,
                )
            elif source.articles_validated < 3:
                # Not enough data — reset to candidate for another round
                source.status = SourceStatus.CANDIDATE
                source.active = False
                source.trust_score = 0.0
                source.probation_start = None
                source.articles_validated = 0
                source.articles_failed = 0
                results["reset"] += 1
                logger.info(
                    "Source '%s' reset to candidate (insufficient data: %d validated)",
                    source.name, source.articles_validated,
                )
            else:
                # Too many failures — reject
                source.status = SourceStatus.REJECTED
                source.active = False
                source.trust_score = 0.0
                source.rejection_reason = (
                    f"Validation ratio {ratio:.2f} < {min_ratio} "
                    f"({source.articles_validated}/{total})"
                )
                results["rejected"] += 1
                logger.info(
                    "Source '%s' rejected (ratio=%.2f, reason: %s)",
                    source.name, ratio, source.rejection_reason,
                )

        session.commit()

    return results


def check_trusted_demotion(engine: Engine) -> int:
    """Demote trusted sources with consecutive validation failures.

    Criteria: articles_failed >= source_demotion_consecutive_failures
    Seed sources are excluded (they query TRUSTED status only).
    """
    threshold = settings.source_demotion_consecutive_failures
    demoted = 0

    with Session(engine) as session:
        sources = session.exec(
            select(Source).where(
                Source.status == SourceStatus.TRUSTED,
                Source.articles_failed >= threshold,
            )
        ).all()

        for source in sources:
            source.status = SourceStatus.PROBATION
            source.trust_score = 0.1
            source.probation_start = datetime.now(UTC)
            source.articles_validated = 0
            source.articles_failed = 0
            demoted += 1
            logger.warning(
                "Source '%s' demoted to probation (%d consecutive failures)",
                source.name, threshold,
            )

        session.commit()

    return demoted
