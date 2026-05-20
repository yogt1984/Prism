"""T4.1: Scheduler orchestration tests.

Covers job registration, interval configuration, and signal shutdown.
"""

import signal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from prism.db import init_db
from prism.main import briefing_cycle, build_scheduler


def test_scheduler_registers_all_jobs():
    scheduler = build_scheduler()
    job_ids = {j.id for j in scheduler.get_jobs()}
    assert job_ids == {"discovery", "analysis", "briefing"}


def test_scheduler_discovery_interval():
    with patch("prism.main.settings") as mock_settings:
        mock_settings.discovery_interval_hours = 2
        scheduler = build_scheduler()

    job = scheduler.get_job("discovery")
    assert isinstance(job.trigger, IntervalTrigger)
    # IntervalTrigger stores interval as timedelta
    assert job.trigger.interval_length == 2 * 3600


def test_scheduler_analysis_interval():
    scheduler = build_scheduler()
    job = scheduler.get_job("analysis")
    assert isinstance(job.trigger, IntervalTrigger)
    assert job.trigger.interval_length == 30 * 60


def test_scheduler_briefing_cron():
    scheduler = build_scheduler()
    job = scheduler.get_job("briefing")
    assert isinstance(job.trigger, CronTrigger)


def test_scheduler_briefing_cron_reads_config():
    """Briefing cron fields come from settings.briefing_schedule_cron."""
    with patch("prism.main.settings") as mock_settings:
        mock_settings.discovery_interval_hours = 1
        mock_settings.briefing_schedule_cron = "30 9 * * 1-5"
        scheduler = build_scheduler()

    job = scheduler.get_job("briefing")
    trigger = job.trigger
    assert isinstance(trigger, CronTrigger)
    # Verify fields parsed from the cron string
    fields = {f.name: str(f) for f in trigger.fields}
    assert fields["minute"] == "30"
    assert fields["hour"] == "9"
    assert fields["day_of_week"] in ("mon-fri", "1-5")


def test_scheduler_briefing_cron_default():
    """Default cron '0 7 * * *' produces hour=7, minute=0."""
    scheduler = build_scheduler()
    job = scheduler.get_job("briefing")
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["minute"] == "0"
    assert fields["hour"] == "7"


def test_scheduler_shutdown_on_signal():
    """SIGINT handler calls scheduler.shutdown()."""
    scheduler = build_scheduler()
    scheduler.shutdown = MagicMock()

    # Retrieve the signal handler that main() would install
    with patch("prism.main.signal.signal") as mock_signal:
        from prism.main import install_signal_handlers
        install_signal_handlers(scheduler)

    # Get the handler that was registered for SIGINT
    sigint_call = [
        call for call in mock_signal.call_args_list
        if call[0][0] == signal.SIGINT
    ]
    assert len(sigint_call) == 1
    handler = sigint_call[0][0][1]

    # Invoke the handler — catches sys.exit(0)
    import pytest
    with pytest.raises(SystemExit):
        handler(signal.SIGINT, None)
    scheduler.shutdown.assert_called_once_with(wait=False)


def test_briefing_cycle_iterates_users():
    """briefing_cycle fetches all users and sends briefings."""
    from prism.models import User

    mock_engine = MagicMock()
    with patch("prism.main.PersonalizationAgent") as mock_p_cls:
        with patch("prism.main.WriterAgent") as mock_w_cls:
            mock_p = mock_p_cls.return_value
            mock_w = mock_w_cls.return_value
            mock_p.get_all_users.return_value = [
                User(email="a@t.com", interests="finance"),
                User(email="b@t.com", interests="tech"),
            ]
            mock_p.select_stories.return_value = []

            briefing_cycle(mock_engine)

            assert mock_p.get_all_users.call_count == 1
            assert mock_p.select_stories.call_count == 2
            assert mock_w.create_and_send.call_count == 2


# --- T8.6: Feedback loop — engagement after briefing ---

@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


def test_briefing_cycle_records_engagement(db_engine):
    """After a sent briefing, engagement is recorded for each delivered cluster."""
    from sqlmodel import Session

    from prism.models import StoryCluster, StoryStatus, User

    with Session(db_engine) as s:
        user = User(id=1, email="a@t.com", interests="finance")
        s.add(user)
        c1 = StoryCluster(id=10, headline="Story A", status=StoryStatus.ANALYZED,
                          article_count=1)
        c2 = StoryCluster(id=20, headline="Story B", status=StoryStatus.ANALYZED,
                          article_count=1)
        s.add(c1)
        s.add(c2)
        s.commit()

    mock_briefing = MagicMock()
    mock_briefing.sent = True

    with patch("prism.main.PersonalizationAgent") as mock_p_cls:
        with patch("prism.main.WriterAgent") as mock_w_cls:
            mock_p = mock_p_cls.return_value
            mock_w = mock_w_cls.return_value
            mock_p.get_all_users.return_value = [
                User(id=1, email="a@t.com", interests="finance"),
            ]
            mock_p.select_stories.return_value = [
                StoryCluster(id=10, headline="Story A"),
                StoryCluster(id=20, headline="Story B"),
            ]
            mock_w.create_and_send.return_value = mock_briefing

            briefing_cycle(db_engine)

            # record_engagement called for each cluster
            assert mock_p.record_engagement.call_count == 2
            calls = mock_p.record_engagement.call_args_list
            cluster_ids = {c.kwargs.get("cluster_id", c[0][1]) for c in calls}
            assert cluster_ids == {10, 20}


def test_briefing_cycle_no_engagement_when_unsent(db_engine):
    """If briefing is not sent, no engagement is recorded."""
    from prism.models import User

    mock_briefing = MagicMock()
    mock_briefing.sent = False

    with patch("prism.main.PersonalizationAgent") as mock_p_cls:
        with patch("prism.main.WriterAgent") as mock_w_cls:
            mock_p = mock_p_cls.return_value
            mock_w = mock_w_cls.return_value
            mock_p.get_all_users.return_value = [
                User(id=1, email="a@t.com", interests="finance"),
            ]
            mock_p.select_stories.return_value = [MagicMock(id=10)]
            mock_w.create_and_send.return_value = mock_briefing

            briefing_cycle(db_engine)

            mock_p.record_engagement.assert_not_called()


def test_briefing_cycle_no_engagement_when_no_stories(db_engine):
    """If no stories selected, create_and_send returns None — no engagement."""
    from prism.models import User

    with patch("prism.main.PersonalizationAgent") as mock_p_cls:
        with patch("prism.main.WriterAgent") as mock_w_cls:
            mock_p = mock_p_cls.return_value
            mock_w = mock_w_cls.return_value
            mock_p.get_all_users.return_value = [
                User(id=1, email="a@t.com", interests="finance"),
            ]
            mock_p.select_stories.return_value = []
            mock_w.create_and_send.return_value = None

            briefing_cycle(db_engine)

            mock_p.record_engagement.assert_not_called()
