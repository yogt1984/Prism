"""T4.1: Scheduler orchestration tests.

Covers job registration, interval configuration, and signal shutdown.
"""

import signal
from unittest.mock import MagicMock, patch

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

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
