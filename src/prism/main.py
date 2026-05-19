"""Main orchestrator — runs all agents on their respective schedules."""

import logging
import signal
import sys

from apscheduler.schedulers.blocking import BlockingScheduler
from sqlalchemy import Engine

from prism.agents.a_ai import AnalysisAgent
from prism.agents.d_ai import DiscoveryAgent
from prism.agents.p_ai import PersonalizationAgent
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


def briefing_cycle(engine: Engine | None = None) -> None:
    try:
        e = engine or get_engine()
        p_ai = PersonalizationAgent()
        w_ai = WriterAgent()

        users = p_ai.get_all_users(e)
        for user in users:
            clusters = p_ai.select_stories(user, e)
            w_ai.create_and_send(user, clusters, e)
    except Exception as exc:
        logger.exception("Briefing cycle failed")
        send_alert(f"Briefing cycle failed: {exc}", level=AlertLevel.ERROR)


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
        briefing_cycle,
        "cron",
        hour=7,
        id="briefing",
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
