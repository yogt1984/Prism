"""Alerting via ntfy.sh push notifications."""

import logging
from enum import StrEnum

import httpx

from prism.config import settings

logger = logging.getLogger(__name__)

NTFY_URL = "https://ntfy.sh"


class AlertLevel(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


_PRIORITY_MAP = {
    AlertLevel.INFO: "3",
    AlertLevel.WARNING: "4",
    AlertLevel.ERROR: "5",
}


def send_alert(message: str, level: AlertLevel = AlertLevel.ERROR) -> None:
    """Send a push notification via ntfy.sh."""
    topic = settings.ntfy_topic
    if not topic:
        return

    try:
        httpx.post(
            f"{NTFY_URL}/{topic}",
            content=message,
            headers={
                "Title": f"Prism {level.value.upper()}: pipeline alert",
                "Priority": _PRIORITY_MAP.get(level, "3"),
                "Tags": f"prism,{level.value}",
            },
        )
        logger.info("Alert sent: %s", message[:80])
    except Exception:
        logger.exception("Failed to send alert: %s", message[:80])
