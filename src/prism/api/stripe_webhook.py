"""Stripe webhook handler — processes events to manage Pro subscriptions."""

import logging
from datetime import UTC, datetime, timedelta

import stripe
from fastapi import APIRouter, HTTPException, Request
from sqlmodel import Session, select

from prism.alerts import AlertLevel, send_alert
from prism.db import get_engine
from prism.models import StripeEvent, User

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Endpoint ─────────────────────────────────────────────────────────


@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict:
    """Handle incoming Stripe webhook events."""
    from prism.config import get_settings

    s = get_settings()

    if not s.stripe_webhook_secret:
        raise HTTPException(
            status_code=503,
            detail="Webhook processing is not configured",
        )

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=s.stripe_webhook_secret,
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payload")

    return _process_event(event)


# ── Event Processing ─────────────────────────────────────────────────


def _process_event(event: dict) -> dict:
    """Route a Stripe event to its handler with idempotency guard."""
    handler = _HANDLERS.get(event["type"])
    if handler is None:
        return {"status": "skipped"}

    with Session(get_engine()) as session:
        existing = session.exec(
            select(StripeEvent).where(StripeEvent.event_id == event["id"])
        ).first()
        if existing:
            return {"status": "duplicate"}

        result = handler(event, session)

        session.add(StripeEvent(
            event_id=event["id"],
            event_type=event["type"],
            user_id=result.get("user_id"),
        ))
        session.commit()

    return {"status": "ok"}


# ── Handlers ─────────────────────────────────────────────────────────


def _handle_checkout_completed(event: dict, session: Session) -> dict:
    """Activate Pro subscription for the user."""
    data = event["data"]["object"]

    prism_user_id = data["metadata"].get("prism_user_id")
    if not prism_user_id:
        logger.warning("checkout.session.completed missing prism_user_id metadata")
        return {}

    user = session.get(User, int(prism_user_id))
    if user is None:
        logger.error("checkout.session.completed: user %s not found", prism_user_id)
        return {}

    user.is_pro = True
    user.stripe_subscription_id = data.get("subscription", "")
    user.pro_until = None
    if user.pro_since is None:
        user.pro_since = datetime.now(UTC)

    session.add(user)

    logger.info(
        "Pro activated for user %s (sub: %s)",
        user.id, user.stripe_subscription_id,
    )
    send_alert(
        f"New Pro subscriber: {user.email} (user {user.id})",
        level=AlertLevel.INFO,
    )

    return {"user_id": user.id}


def _find_user_by_subscription(sub_id: str, session: Session) -> User | None:
    """Look up user by stripe_subscription_id."""
    if not sub_id:
        return None
    return session.exec(
        select(User).where(User.stripe_subscription_id == sub_id)
    ).first()


def _handle_invoice_paid(event: dict, session: Session) -> dict:
    """Confirm renewal — clear any grace period."""
    data = event["data"]["object"]
    sub_id = data.get("subscription")

    user = _find_user_by_subscription(sub_id, session)
    if user is None:
        logger.warning("invoice.paid: no user for subscription %s", sub_id)
        return {}

    user.pro_until = None
    user.is_pro = True
    session.add(user)

    logger.info("Renewal confirmed for user %s", user.id)
    return {"user_id": user.id}


def _handle_invoice_payment_failed(event: dict, session: Session) -> dict:
    """Start grace period — user keeps Pro for grace_period_days."""
    from prism.config import get_settings

    data = event["data"]["object"]
    sub_id = data.get("subscription")

    user = _find_user_by_subscription(sub_id, session)
    if user is None:
        logger.warning("invoice.payment_failed: no user for sub %s", sub_id)
        return {}

    grace_days = get_settings().grace_period_days
    user.pro_until = datetime.now(UTC) + timedelta(days=grace_days)
    session.add(user)

    logger.warning(
        "Payment failed for user %s, grace period until %s",
        user.id, user.pro_until,
    )
    send_alert(
        f"Payment failed for {user.email} (user {user.id}). "
        f"Grace period: {grace_days} days.",
        level=AlertLevel.WARNING,
    )

    return {"user_id": user.id}


def _handle_subscription_deleted(event: dict, session: Session) -> dict:
    """Subscription cancelled — start grace period for downgrade."""
    from prism.config import get_settings

    data = event["data"]["object"]
    sub_id = data.get("id")

    user = _find_user_by_subscription(sub_id, session)
    if user is None:
        logger.warning("subscription.deleted: no user for sub %s", sub_id)
        return {}

    grace_days = get_settings().grace_period_days
    user.pro_until = datetime.now(UTC) + timedelta(days=grace_days)
    user.stripe_subscription_id = ""
    session.add(user)

    logger.info(
        "Subscription cancelled for user %s, grace until %s",
        user.id, user.pro_until,
    )
    send_alert(
        f"Subscription cancelled: {user.email} (user {user.id}). "
        f"Pro access until {user.pro_until.strftime('%Y-%m-%d')}.",
        level=AlertLevel.WARNING,
    )

    return {"user_id": user.id}


_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_failed": _handle_invoice_payment_failed,
    "customer.subscription.deleted": _handle_subscription_deleted,
}
