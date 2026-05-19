"""T5.2: Monitoring and alerting tests.

Covers ntfy.sh push notifications on pipeline failures.
"""

import logging
from unittest.mock import MagicMock, patch

from prism.alerts import AlertLevel, send_alert


def _with_topic():
    """Patch settings to have a non-empty ntfy_topic."""
    return patch("prism.alerts.settings", MagicMock(ntfy_topic="prism-test"))


def test_alert_sends_to_ntfy():
    with _with_topic(), patch("prism.alerts.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        send_alert("Test alert", level=AlertLevel.ERROR)

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert "ntfy.sh" in call_kwargs[0][0]


def test_alert_includes_message():
    with _with_topic(), patch("prism.alerts.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        send_alert("Discovery failed: Brave API down", level=AlertLevel.ERROR)

    body = mock_post.call_args[1]["content"]
    assert "Discovery failed" in body


def test_alert_includes_level_in_title():
    with _with_topic(), patch("prism.alerts.httpx.post") as mock_post:
        mock_post.return_value = MagicMock(status_code=200)
        send_alert("Zero clusters", level=AlertLevel.WARNING)

    headers = mock_post.call_args[1]["headers"]
    assert "WARNING" in headers["Title"]


def test_alert_failure_does_not_crash(caplog):
    """Alert delivery failure should be logged, not raised."""
    with _with_topic(), patch("prism.alerts.httpx.post", side_effect=Exception("ntfy down")):
        with caplog.at_level(logging.ERROR):
            send_alert("test", level=AlertLevel.ERROR)

    assert "Failed to send alert" in caplog.text


def test_alert_skipped_when_no_topic():
    """If ntfy_topic is empty, alerts are silently skipped."""
    with patch("prism.alerts.settings") as mock_settings:
        mock_settings.ntfy_topic = ""
        with patch("prism.alerts.httpx.post") as mock_post:
            send_alert("test", level=AlertLevel.ERROR)

    mock_post.assert_not_called()


# --- Integration: alerts from cycle wrappers ---

def test_discovery_failure_triggers_alert():
    from prism.main import discovery_cycle

    with patch("prism.main.DiscoveryAgent") as mock_cls:
        mock_cls.return_value.run_discovery.side_effect = Exception("boom")
        with patch("prism.main.send_alert") as mock_alert:
            discovery_cycle(MagicMock())

    mock_alert.assert_called_once()
    assert "Discovery" in mock_alert.call_args[0][0]


def test_analysis_failure_triggers_alert():
    from prism.main import analysis_cycle

    with patch("prism.main.AnalysisAgent") as mock_cls:
        mock_cls.return_value.process_pending.side_effect = Exception("boom")
        with patch("prism.main.send_alert") as mock_alert:
            analysis_cycle(MagicMock())

    mock_alert.assert_called_once()
    assert "Analysis" in mock_alert.call_args[0][0]


def test_briefing_failure_triggers_alert():
    from prism.main import briefing_cycle

    with patch("prism.main.PersonalizationAgent") as mock_p:
        mock_p.return_value.get_all_users.side_effect = Exception("boom")
        with patch("prism.main.WriterAgent"):
            with patch("prism.main.send_alert") as mock_alert:
                briefing_cycle(MagicMock())

    mock_alert.assert_called_once()
    assert "Briefing" in mock_alert.call_args[0][0]
