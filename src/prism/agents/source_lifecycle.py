"""Source lifecycle management — probation promotion and evaluation."""

import logging
from datetime import UTC, datetime

from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.models import Source, SourceStatus

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
