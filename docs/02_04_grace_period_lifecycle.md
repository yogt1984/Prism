# 02_04 — Grace Period & Subscription Lifecycle

**Parent:** 02 Stripe Payment Integration
**Depends on:** 02_01 (schema), 02_03 (webhook sets `pro_until`)

---

## Objective

Implement the background job that downgrades users after their grace period
expires, the Stripe Customer Portal endpoint for self-service subscription
management, and the full lifecycle logic that ties the Stripe events together
into a coherent state machine.

---

## Subscription State Machine

```
                    checkout.session.completed
  FREE ──────────────────────────────────────────> ACTIVE
   ^                                                  |
   |                                                  |
   | expiry_job                    invoice.paid        | invoice.payment_failed
   | (pro_until < now)             (clears grace)      | (sets pro_until)
   |                                    |              |
   |                                    v              v
   └─────────── EXPIRED <─────── GRACE PERIOD <────────┘
                   ^                    ^
                   |                    |
                   | expiry_job         | customer.subscription.deleted
                   |                    |
                   └────────────────────┘
```

**State is derived, not stored.** The state comes from reading these fields:

| State | `is_pro` | `stripe_subscription_id` | `pro_until` |
|-------|----------|--------------------------|-------------|
| FREE | `False` | `""` | `None` |
| ACTIVE | `True` | `"sub_xxx"` | `None` |
| GRACE | `True` | `""` or `"sub_xxx"` | future datetime |
| EXPIRED | `False` | `""` | past datetime |

---

## Background Expiry Job

### Purpose

Check all users with an active grace period (`pro_until` set and in the past)
and downgrade them to free tier.

### Implementation

File: `src/prism/subscription.py` (new module)

```python
"""Subscription lifecycle management."""

import logging
from datetime import UTC, datetime

from sqlmodel import Session, select

from prism.alerts import AlertLevel, send_alert
from prism.models import User

logger = logging.getLogger(__name__)


def expire_grace_periods(engine) -> int:
    """Downgrade users whose grace period has ended.

    Returns:
        Number of users downgraded.
    """
    now = datetime.now(UTC)
    count = 0

    with Session(engine) as session:
        # Find users with expired grace period
        stmt = select(User).where(
            User.is_pro == True,            # noqa: E712 — SQLAlchemy requires ==
            User.pro_until != None,         # noqa: E711 — SQLAlchemy requires !=
            User.pro_until < now,
        )
        expired_users = session.exec(stmt).all()

        for user in expired_users:
            user.is_pro = False
            user.stripe_subscription_id = ""  # clear stale subscription
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
```

### Scheduler Integration

Add to `src/prism/main.py` in `build_scheduler()`:

```python
from prism.subscription import expire_grace_periods

def grace_period_check(engine: Engine | None = None) -> None:
    try:
        count = expire_grace_periods(engine or get_engine())
        if count > 0:
            logger.info("Grace period check: %d user(s) downgraded", count)
    except Exception as exc:
        logger.exception("Grace period check failed")
        send_alert(f"Grace period check failed: {exc}", level=AlertLevel.ERROR)

# In build_scheduler():
scheduler.add_job(
    grace_period_check,
    "cron",
    hour="0",                    # midnight UTC daily
    minute="15",                 # offset from other cron jobs
    id="grace_period_check",
)
```

**Schedule:** daily at 00:15 UTC. Offset from the briefing job (07:00 UTC)
to avoid concurrent DB writes.

### Edge Cases

| Scenario | Behavior |
|----------|----------|
| User pays during grace period | `invoice.paid` webhook clears `pro_until` before expiry job runs |
| User re-subscribes during grace | `checkout.session.completed` sets `is_pro=True`, clears `pro_until` |
| Expiry job runs while payment is processing | Grace period is 7 days — ample time for retries |
| Multiple failed payments | Each `invoice.payment_failed` resets `pro_until` to now + 7 days |
| User already free when job runs | Query only selects `is_pro=True` — no action on free users |

---

## Stripe Customer Portal Endpoint

### POST /users/{user_id}/portal

Lets Pro users manage their subscription (cancel, update payment, view invoices)
via Stripe's hosted Customer Portal.

**Authentication:** `X-API-Key` header
**Authorization:** own account only, must be Pro with `stripe_customer_id`

**Response (200):**
```json
{
  "portal_url": "https://billing.stripe.com/p/session/..."
}
```

**Error responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 401 | Missing/invalid API key | `{"detail": "Missing API key"}` |
| 403 | Not Pro or not the resource owner | `{"detail": "..."}` |
| 404 | User not found | `{"detail": "User not found"}` |
| 409 | No Stripe customer (never subscribed) | `{"detail": "No subscription to manage"}` |
| 503 | Stripe not configured | `{"detail": "Payment processing is not configured"}` |
| 502 | Stripe API error | `{"detail": "Billing portal temporarily unavailable"}` |

### Implementation

Add to `src/prism/api/routes.py`:

```python
class PortalResponse(BaseModel):
    portal_url: str


@router.post("/users/{user_id}/portal", response_model=PortalResponse)
def create_portal_session(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for subscription management."""
    if auth_user.id != user_id:
        raise HTTPException(status_code=403,
            detail="Access denied: you can only access your own resources")

    from prism.config import get_settings
    s = get_settings()
    if not s.stripe_secret_key:
        raise HTTPException(status_code=503,
            detail="Payment processing is not configured")

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.stripe_customer_id:
        raise HTTPException(status_code=409,
            detail="No subscription to manage")

    import stripe
    stripe.api_key = s.stripe_secret_key

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{s.frontend_url}/settings",
        )
    except stripe.StripeError as exc:
        raise HTTPException(status_code=502,
            detail="Billing portal temporarily unavailable") from exc

    return PortalResponse(portal_url=portal_session.url)
```

### Stripe Portal Configuration (One-Time Setup)

Configure in Stripe Dashboard → Settings → Customer Portal:

- **Subscriptions:** allow cancel, allow switch plans (if future plans added)
- **Payment methods:** allow update
- **Invoices:** show invoice history
- **Branding:** Prism logo, brand colors
- **Return URL:** `https://yourdomain.com/settings`

---

## CLI Command

Add a manual trigger for the grace period check:

```
prism subscription expire    — run grace period check manually
prism subscription status    — show all users with active grace periods
```

### Implementation

File: `src/prism/cli/subscription.py`

```python
import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(help="Subscription lifecycle management.")
console = Console()

@app.command()
def expire():
    """Run grace period expiry check."""
    from prism.db import get_engine
    from prism.subscription import expire_grace_periods
    count = expire_grace_periods(get_engine())
    console.print(f"Downgraded {count} user(s).")

@app.command()
def status():
    """Show users with active or expired grace periods."""
    from prism.db import get_engine
    from prism.models import User
    from sqlmodel import Session, select

    with Session(get_engine()) as session:
        users = session.exec(
            select(User).where(User.pro_until != None)  # noqa: E711
        ).all()

    if not users:
        console.print("No users with grace periods.")
        return

    table = Table(title="Grace Period Status")
    table.add_column("ID")
    table.add_column("Email")
    table.add_column("Pro?")
    table.add_column("Grace Until")
    table.add_column("Status")

    from datetime import UTC, datetime
    now = datetime.now(UTC)
    for u in users:
        expired = u.pro_until < now if u.pro_until else False
        table.add_row(
            str(u.id), u.email, str(u.is_pro),
            str(u.pro_until), "EXPIRED" if expired else "ACTIVE",
        )
    console.print(table)
```

Register in the main CLI app alongside existing command groups.

---

## Full Lifecycle Walkthrough

### Happy Path (Subscribe → Renew → Continue)

```
1. User clicks "Upgrade"
   → POST /users/5/checkout → Stripe Checkout page
2. User completes payment
   → Stripe fires checkout.session.completed
   → Webhook: is_pro=True, stripe_subscription_id="sub_xxx", pro_since=now
3. 30 days later, Stripe charges card
   → Stripe fires invoice.paid
   → Webhook: pro_until=None (no-op, already clear)
4. Repeat step 3 monthly
```

### Payment Failure → Recovery

```
1. Stripe tries to charge, card declined
   → Stripe fires invoice.payment_failed
   → Webhook: pro_until = now + 7 days, is_pro stays True
2. Stripe retries 3 times over ~7 days (configurable in Stripe)
3a. Card succeeds on retry:
   → Stripe fires invoice.paid
   → Webhook: pro_until=None (grace cleared), is_pro=True
3b. All retries fail:
   → Stripe fires customer.subscription.deleted
   → Webhook: pro_until = now + 7 days, stripe_subscription_id=""
4. Grace period expiry job runs (daily):
   → Finds user with pro_until < now
   → Sets is_pro=False
   → User is now FREE
```

### Cancel → Resubscribe

```
1. Pro user clicks "Manage Subscription"
   → POST /users/5/portal → Stripe Customer Portal
2. User clicks "Cancel" in portal
   → Stripe fires customer.subscription.deleted
   → Webhook: pro_until = now + 7 days, stripe_subscription_id=""
3. Within 7 days, user clicks "Upgrade" again
   → POST /users/5/checkout (reuses existing stripe_customer_id)
   → User completes payment
   → checkout.session.completed: is_pro=True, pro_until=None, new sub ID
4. User is back to ACTIVE
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Expiry job downgrades users with `pro_until < now` | Create user with past `pro_until`, run job, verify `is_pro=False` |
| 2 | Expiry job ignores users with future `pro_until` | Create user with future `pro_until`, run job, verify `is_pro=True` |
| 3 | Expiry job ignores free users | Create free user with `pro_until=None`, run job, verify no change |
| 4 | Expiry job clears `stripe_subscription_id` | Verify field is empty after downgrade |
| 5 | ntfy alert fires when users are downgraded | Mock alerts, verify `send_alert` called with count |
| 6 | Portal endpoint returns valid Stripe URL | Call endpoint, verify URL contains `billing.stripe.com` |
| 7 | Portal returns 409 for user without `stripe_customer_id` | New user calls portal, verify 409 |
| 8 | Portal returns 403 for wrong user | Cross-user call, verify 403 |
| 9 | Job runs daily at 00:15 UTC | Check scheduler job list for `grace_period_check` |
| 10 | `prism subscription expire` CLI works | Run command, verify output and DB state |
| 11 | `prism subscription status` shows grace periods | Create users with grace periods, verify table output |
| 12 | Payment during grace period restores Pro | Set `pro_until`, send `invoice.paid` webhook, verify `pro_until=None` |
| 13 | Cancel + re-subscribe reuses customer ID | Full lifecycle, verify same `stripe_customer_id` |
| 14 | Multiple payment failures don't stack grace periods | Send 3 `invoice.payment_failed`, verify single 7-day window from latest |

---

## Testing Strategy

### Unit Tests

```python
def test_expire_downgrades_past_grace(engine, session):
    """User with pro_until in the past gets downgraded."""
    user = create_user(is_pro=True, pro_until=datetime(2026, 1, 1, tzinfo=UTC))
    count = expire_grace_periods(engine)
    assert count == 1
    session.refresh(user)
    assert user.is_pro is False

def test_expire_skips_future_grace(engine, session):
    """User with future pro_until stays Pro."""
    user = create_user(is_pro=True, pro_until=datetime(2099, 1, 1, tzinfo=UTC))
    count = expire_grace_periods(engine)
    assert count == 0
    session.refresh(user)
    assert user.is_pro is True

def test_expire_skips_free_users(engine):
    """Free users are not affected."""
    create_user(is_pro=False, pro_until=None)
    count = expire_grace_periods(engine)
    assert count == 0

def test_portal_creates_session(mock_stripe, pro_user, client):
    """Pro user gets a portal URL."""
    mock_stripe.billing_portal.Session.create.return_value = Mock(
        url="https://billing.stripe.com/p/session/test_123"
    )
    res = client.post(f"/users/{pro_user.id}/portal",
                      headers={"X-API-Key": pro_user_key})
    assert res.status_code == 200
    assert "billing.stripe.com" in res.json()["portal_url"]

def test_portal_rejects_no_customer(free_user, client):
    """User without stripe_customer_id gets 409."""
    res = client.post(f"/users/{free_user.id}/portal",
                      headers={"X-API-Key": free_user_key})
    assert res.status_code == 409
```

### Integration Test

Full lifecycle test with Stripe test mode:
1. Create checkout → complete payment (test card)
2. Verify `is_pro=True`
3. Simulate `invoice.payment_failed`
4. Verify grace period set
5. Run expiry job (with mocked time past grace)
6. Verify `is_pro=False`
7. Re-subscribe → verify `is_pro=True` again

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/subscription.py` | New: `expire_grace_periods()` |
| `src/prism/main.py` | Add `grace_period_check` job to scheduler |
| `src/prism/api/routes.py` | Add `POST /users/{id}/portal` endpoint |
| `src/prism/cli/subscription.py` | New: `expire` and `status` commands |
| `src/prism/cli/app.py` | Register `subscription` command group |
| `tests/test_subscription.py` | New test file |
| `tests/test_api_portal.py` | New test file |
