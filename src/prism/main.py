"""Main orchestrator — runs all agents on their respective schedules."""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import Engine

from prism.agents.a_ai import AnalysisAgent
from prism.agents.d_ai import DiscoveryAgent
from prism.agents.p_ai import PersonalizationAgent
from prism.agents.r_ai import ResonanceTracker
from prism.agents.w_ai import WriterAgent
from prism.alerts import AlertLevel, send_alert
from prism.config import settings
from prism.db import get_engine, init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def discovery_cycle(engine: Engine | None = None) -> None:
    try:
        d_ai = DiscoveryAgent()
        d_ai.run_discovery(engine=engine or get_engine())
    except Exception as exc:
        logger.exception("Discovery cycle failed")
        send_alert(f"Discovery cycle failed: {exc}", level=AlertLevel.ERROR)


def analysis_cycle(engine: Engine | None = None) -> None:
    try:
        a_ai = AnalysisAgent()
        a_ai.process_pending(engine or get_engine())
    except Exception as exc:
        logger.exception("Analysis cycle failed")
        send_alert(f"Analysis cycle failed: {exc}", level=AlertLevel.ERROR)


def perception_cycle(engine: Engine | None = None) -> None:
    try:
        r_ai = ResonanceTracker()
        r_ai.process_keywords(engine or get_engine())
    except Exception as exc:
        logger.exception("Perception cycle failed")
        send_alert(f"Perception cycle failed: {exc}", level=AlertLevel.ERROR)


def briefing_cycle(engine: Engine | None = None) -> None:
    try:
        e = engine or get_engine()
        p_ai = PersonalizationAgent()
        w_ai = WriterAgent()

        users = p_ai.get_all_users(e)
        for user in users:
            clusters = p_ai.select_stories(user, e)
            briefing = w_ai.create_and_send(user, clusters, e)
            if briefing and briefing.sent:
                for cluster in clusters:
                    p_ai.record_engagement(
                        user.id, cluster.id, "delivered", engine=e,  # type: ignore[arg-type]
                    )
    except Exception as exc:
        logger.exception("Briefing cycle failed")
        send_alert(f"Briefing cycle failed: {exc}", level=AlertLevel.ERROR)


def source_evaluation(engine: Engine | None = None) -> None:
    try:
        from prism.agents.source_lifecycle import (
            check_trusted_demotion,
            evaluate_probation_sources,
        )

        e = engine or get_engine()
        results = evaluate_probation_sources(e)
        demoted = check_trusted_demotion(e)
        logger.info(
            "Source evaluation: promoted=%d, rejected=%d, reset=%d, demoted=%d",
            results["promoted"], results["rejected"], results["reset"], demoted,
        )
    except Exception as exc:
        logger.exception("Source evaluation failed")
        send_alert(f"Source evaluation failed: {exc}", level=AlertLevel.ERROR)


def grace_period_check(engine: Engine | None = None) -> None:
    try:
        from prism.subscription import expire_grace_periods

        count = expire_grace_periods(engine or get_engine())
        if count > 0:
            logger.info("Grace period check: %d user(s) downgraded", count)
    except Exception as exc:
        logger.exception("Grace period check failed")
        send_alert(f"Grace period check failed: {exc}", level=AlertLevel.ERROR)


def build_scheduler() -> BlockingScheduler:
    """Create and configure the scheduler without starting it."""
    scheduler = BlockingScheduler()

    scheduler.add_job(
        discovery_cycle,
        "interval",
        hours=settings.discovery_interval_hours,
        id="discovery",
    )

    scheduler.add_job(
        analysis_cycle,
        "interval",
        minutes=30,
        id="analysis",
    )

    scheduler.add_job(
        perception_cycle,
        "interval",
        minutes=settings.perception_scan_interval_minutes,
        id="perception",
    )

    # Parse "min hour dom month dow" cron expression from config
    cron_parts = settings.briefing_schedule_cron.split()
    scheduler.add_job(
        briefing_cycle,
        "cron",
        minute=cron_parts[0] if len(cron_parts) > 0 else "0",
        hour=cron_parts[1] if len(cron_parts) > 1 else "7",
        day=cron_parts[2] if len(cron_parts) > 2 else "*",
        month=cron_parts[3] if len(cron_parts) > 3 else "*",
        day_of_week=cron_parts[4] if len(cron_parts) > 4 else "*",
        id="briefing",
    )

    scheduler.add_job(
        source_evaluation,
        "cron",
        hour="0",
        minute="30",
        id="source_evaluation",
    )

    scheduler.add_job(
        grace_period_check,
        "cron",
        hour="0",
        minute="15",
        id="grace_period_check",
    )

    return scheduler


def install_signal_handlers(scheduler: BlockingScheduler) -> None:
    """Register SIGINT/SIGTERM for graceful shutdown."""
    def shutdown(signum, frame):  # type: ignore[no-untyped-def]
        logger.info("Shutting down (signal %s)...", signum)
        scheduler.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)


def main() -> None:
    logger.info("Initializing Prism pipeline...")
    init_db()

    scheduler = build_scheduler()
    install_signal_handlers(scheduler)

    logger.info("Pipeline started. Schedules active.")
    scheduler.start()


if __name__ == "__main__":
    main()
