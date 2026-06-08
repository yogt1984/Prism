"""Subscription lifecycle management."""

import logging
from datetime import UTC, datetime

from sqlmodel import Session, select

from prism.alerts import AlertLevel, send_alert
from prism.models import User

logger = logging.getLogger(__name__)


def expire_grace_periods(engine) -> int:  # type: ignore[no-untyped-def]
    """Downgrade users whose grace period has ended.

    Returns:
        Number of users downgraded.
    """
    now = datetime.now(UTC)
    count = 0

    with Session(engine) as session:
        stmt = select(User).where(
            User.is_pro == True,       # noqa: E712 — SQLAlchemy requires ==
            User.pro_until != None,    # noqa: E711 — SQLAlchemy requires !=
            User.pro_until < now,
        )
        expired_users = session.exec(stmt).all()

        for user in expired_users:
            user.is_pro = False
            user.stripe_subscription_id = ""
            session.add(user)

            logger.info(
                "Grace period expired for user %s (%s). Downgraded to free.",
                user.id, user.email,
            )
            count += 1

        if count > 0:
            session.commit()

    if count > 0:
        send_alert(
            f"Grace period expired: {count} user(s) downgraded to free tier.",
            level=AlertLevel.WARNING,
        )

    return count
