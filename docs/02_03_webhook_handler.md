# 02_03 — Stripe Webhook Handler

**Parent:** 02 Stripe Payment Integration
**Depends on:** 02_01 (schema: StripeEvent table, User Stripe fields)

---

## Objective

Implement the webhook endpoint that receives Stripe events and updates user
subscription state. This is the most critical piece of the payment system —
it's the only mechanism that transitions `is_pro` between `True` and `False`.

---

## Endpoint Specification

### POST /webhooks/stripe

**Authentication:** Stripe signature verification (NOT API key auth)
**Content-Type:** `application/json` (raw body required for signature check)

**Response (200):** `{"status": "ok"}` for all successfully processed events
**Response (200):** `{"status": "skipped"}` for unhandled event types
**Response (200):** `{"status": "duplicate"}` for already-processed events
**Response (400):** `{"detail": "Invalid signature"}` for failed verification

**Always return 200 for handled/skipped events.** Stripe retries on non-2xx,
so returning 4xx/5xx for business logic issues causes infinite retries.

---

## Handled Event Types

| Event | Trigger | Action |
|-------|---------|--------|
| `checkout.session.completed` | User completes payment | Activate Pro |
| `invoice.paid` | Monthly renewal succeeds | Clear grace period |
| `invoice.payment_failed` | Card declined on renewal | Start grace period |
| `customer.subscription.deleted` | Subscription cancelled (by user or system) | Start grace period |

All other event types return `{"status": "skipped"}` with 200.

---

## Implementation

File: `src/prism/api/stripe_webhook.py` (new file, separate from routes.py)

### Signature Verification

```python
import stripe
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request) -> dict:
    """Handle incoming Stripe webhook events."""
    from prism.config import get_settings
    s = get_settings()

    if not s.stripe_webhook_secret:
        raise HTTPException(status_code=503,
            detail="Webhook processing is not configured")

    # 1. Read raw body (required for signature verification)
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # 2. Verify signature
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

    # 3. Process event
    return _process_event(event)
```

**Why `async def`:** the signature verification needs the raw request body
via `await request.body()`. Even though the rest is synchronous, FastAPI
handles this correctly.

### Event Router

```python
from prism.db import get_engine
from prism.models import StripeEvent, User
from sqlmodel import Session, select

_HANDLERS = {
    "checkout.session.completed": _handle_checkout_completed,
    "invoice.paid": _handle_invoice_paid,
    "invoice.payment_failed": _handle_invoice_payment_failed,
    "customer.subscription.deleted": _handle_subscription_deleted,
}

def _process_event(event: dict) -> dict:
    """Route a Stripe event to its handler with idempotency guard."""
    handler = _HANDLERS.get(event["type"])
    if handler is None:
        return {"status": "skipped"}

    with Session(get_engine()) as session:
        # Idempotency check
        existing = session.exec(
            select(StripeEvent).where(StripeEvent.event_id == event["id"])
        ).first()
        if existing:
            return {"status": "duplicate"}

        # Process
        result = handler(event, session)

        # Record event
        session.add(StripeEvent(
            event_id=event["id"],
            event_type=event["type"],
            user_id=result.get("user_id"),
        ))
        session.commit()

    return {"status": "ok"}
```

### Event Handlers

#### `checkout.session.completed`

Fired when user completes payment on the Stripe Checkout page.

```python
def _handle_checkout_completed(event: dict, session: Session) -> dict:
    """Activate Pro subscription for the user."""
    data = event["data"]["object"]         # Checkout Session object

    # Find user via metadata
    prism_user_id = data["metadata"].get("prism_user_id")
    if not prism_user_id:
        logger.warning("checkout.session.completed missing prism_user_id metadata")
        return {}

    user = session.get(User, int(prism_user_id))
    if user is None:
        logger.error("checkout.session.completed: user %s not found", prism_user_id)
        return {}

    # Activate Pro
    user.is_pro = True
    user.stripe_subscription_id = data.get("subscription", "")
    user.pro_until = None                  # clear any grace period
    if user.pro_since is None:
        user.pro_since = datetime.now(UTC) # first activation only

    session.add(user)

    logger.info("Pro activated for user %s (sub: %s)",
                user.id, user.stripe_subscription_id)

    # Send alert
    send_alert(
        f"New Pro subscriber: {user.email} (user {user.id})",
        level=AlertLevel.INFO,
    )

    return {"user_id": user.id}
```

**Data extracted from Checkout Session object:**

| Field | Path | Example |
|-------|------|---------|
| User ID | `data.object.metadata.prism_user_id` | `"5"` |
| Subscription ID | `data.object.subscription` | `"sub_xxx"` |
| Customer ID | `data.object.customer` | `"cus_xxx"` |

#### `invoice.paid`

Fired on each successful monthly payment (including the first).

```python
def _handle_invoice_paid(event: dict, session: Session) -> dict:
    """Confirm renewal — clear any grace period."""
    data = event["data"]["object"]         # Invoice object
    sub_id = data.get("subscription")
    if not sub_id:
        return {}

    user = session.exec(
        select(User).where(User.stripe_subscription_id == sub_id)
    ).first()
    if user is None:
        logger.warning("invoice.paid: no user for subscription %s", sub_id)
        return {}

    user.pro_until = None                  # clear grace period
    user.is_pro = True                     # ensure Pro is active
    session.add(user)

    logger.info("Renewal confirmed for user %s", user.id)
    return {"user_id": user.id}
```

#### `invoice.payment_failed`

Fired when a renewal payment is declined.

```python
def _handle_invoice_payment_failed(event: dict, session: Session) -> dict:
    """Start grace period — user keeps Pro for grace_period_days."""
    from prism.config import get_settings

    data = event["data"]["object"]
    sub_id = data.get("subscription")
    if not sub_id:
        return {}

    user = session.exec(
        select(User).where(User.stripe_subscription_id == sub_id)
    ).first()
    if user is None:
        logger.warning("invoice.payment_failed: no user for sub %s", sub_id)
        return {}

    grace_days = get_settings().grace_period_days
    user.pro_until = datetime.now(UTC) + timedelta(days=grace_days)
    # is_pro stays True during grace period
    session.add(user)

    logger.warning("Payment failed for user %s, grace period until %s",
                   user.id, user.pro_until)

    send_alert(
        f"Payment failed for {user.email} (user {user.id}). "
        f"Grace period: {grace_days} days.",
        level=AlertLevel.WARNING,
    )

    return {"user_id": user.id}
```

#### `customer.subscription.deleted`

Fired when a subscription is cancelled (by user via portal or by Stripe
due to repeated payment failures).

```python
def _handle_subscription_deleted(event: dict, session: Session) -> dict:
    """Subscription cancelled — start grace period for downgrade."""
    from prism.config import get_settings

    data = event["data"]["object"]         # Subscription object
    sub_id = data.get("id")

    user = session.exec(
        select(User).where(User.stripe_subscription_id == sub_id)
    ).first()
    if user is None:
        logger.warning("subscription.deleted: no user for sub %s", sub_id)
        return {}

    grace_days = get_settings().grace_period_days
    user.pro_until = datetime.now(UTC) + timedelta(days=grace_days)
    user.stripe_subscription_id = ""       # clear — no active subscription
    session.add(user)

    logger.info("Subscription cancelled for user %s, grace until %s",
                user.id, user.pro_until)

    send_alert(
        f"Subscription cancelled: {user.email} (user {user.id}). "
        f"Pro access until {user.pro_until.strftime('%Y-%m-%d')}.",
        level=AlertLevel.WARNING,
    )

    return {"user_id": user.id}
```

---

## User Lookup Strategy

Different events carry user identity differently:

| Event | Lookup field | Source |
|-------|-------------|--------|
| `checkout.session.completed` | `metadata.prism_user_id` | Set during checkout creation (02_02) |
| `invoice.paid` | `subscription` ID | Match against `User.stripe_subscription_id` |
| `invoice.payment_failed` | `subscription` ID | Match against `User.stripe_subscription_id` |
| `customer.subscription.deleted` | subscription `id` | Match against `User.stripe_subscription_id` |

**Fallback:** if subscription-based lookup fails, try
`data.object.customer` → `User.stripe_customer_id`. Log a warning.

---

## Register Webhook Router

In `src/prism/api/app.py`, include the webhook router:

```python
from prism.api.stripe_webhook import router as stripe_router

app.include_router(stripe_router)
```

**Important:** the webhook endpoint must NOT use the rate limiter middleware
(Stripe sends legitimate bursts). Exclude `/webhooks/stripe` from rate
limiting in `rate_limit.py`.

---

## Idempotency Guarantees

| Scenario | Behavior |
|----------|----------|
| Same event_id received twice | Second call returns `{"status": "duplicate"}`, no DB changes |
| Event for unknown user | Logged as warning, returns `{"status": "ok"}` (no retry) |
| Event for unknown subscription | Logged as warning, returns `{"status": "ok"}` |
| DB commit fails | Returns 500, Stripe retries (event not in StripeEvent table) |
| Signature invalid | Returns 400, Stripe retries with correct signature |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Valid checkout.session.completed sets `is_pro=True` | Send event via Stripe CLI, query DB |
| 2 | Valid checkout.session.completed stores `stripe_subscription_id` | Verify User row has `sub_xxx` |
| 3 | `pro_since` set on first activation only | Activate, cancel, reactivate — `pro_since` unchanged |
| 4 | invoice.paid clears `pro_until` | Set grace period, send invoice.paid, verify `pro_until=None` |
| 5 | invoice.payment_failed sets `pro_until` to now + 7 days | Send event, verify `pro_until` within 1 second of expected |
| 6 | subscription.deleted clears `stripe_subscription_id` | Send event, verify field is empty |
| 7 | subscription.deleted sets grace period | Send event, verify `pro_until` is set |
| 8 | Duplicate event_id returns "duplicate" | Send same event twice, verify second returns duplicate |
| 9 | Duplicate event causes no DB changes | Check User row unchanged between first and second call |
| 10 | Invalid signature returns 400 | Send request with wrong signature, verify 400 |
| 11 | Unknown event type returns "skipped" | Send `charge.succeeded`, verify 200 + skipped |
| 12 | ntfy alert fires on Pro activation | Mock alerts, verify `send_alert` called |
| 13 | ntfy alert fires on payment failure | Mock alerts, verify warning-level alert |
| 14 | Webhook excluded from rate limiter | Send 200 events in 1 minute, verify no 429 |

---

## Testing Strategy

### Unit Tests

```python
def test_checkout_completed_activates_pro(session, free_user):
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(free_user.id)},
        "subscription": "sub_test_123",
    })
    result = _process_event(event)
    assert result["status"] == "ok"
    session.refresh(free_user)
    assert free_user.is_pro is True
    assert free_user.stripe_subscription_id == "sub_test_123"

def test_invoice_failed_sets_grace_period(session, pro_user):
    event = make_event("invoice.payment_failed", {
        "subscription": pro_user.stripe_subscription_id,
    })
    _process_event(event)
    session.refresh(pro_user)
    assert pro_user.pro_until is not None
    assert pro_user.is_pro is True  # still Pro during grace

def test_duplicate_event_is_skipped(session, free_user):
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(free_user.id)},
        "subscription": "sub_test_456",
    })
    _process_event(event)
    result = _process_event(event)  # second call
    assert result["status"] == "duplicate"

def test_invalid_signature_returns_400(client):
    res = client.post("/webhooks/stripe",
        content=b'{}', headers={"stripe-signature": "bad"})
    assert res.status_code == 400
```

### Integration Test (Stripe CLI)

```bash
# Terminal 1: forward webhooks
stripe listen --forward-to localhost:8000/webhooks/stripe

# Terminal 2: trigger test events
stripe trigger checkout.session.completed
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.deleted
```

Verify DB state after each trigger.

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/stripe_webhook.py` | New file: webhook endpoint + 4 handlers |
| `src/prism/api/app.py` | Include stripe_router |
| `src/prism/api/rate_limit.py` | Exclude `/webhooks/stripe` from rate limiting |
| `tests/test_webhook_stripe.py` | New test file |
