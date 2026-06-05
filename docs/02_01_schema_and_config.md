# 02_01 — Database Schema & Stripe Configuration

**Parent:** 02 Stripe Payment Integration
**Must complete before:** all other 02_xx specs (schema is the foundation)

---

## Objective

Add the Stripe-related fields to the `User` model, create a webhook event
log table for idempotent processing, run an Alembic migration, and wire
Stripe credentials into the existing `config.py` settings.

---

## Current User Model (`src/prism/models.py:104-114`)

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = ""
    interests: str = ""
    preferred_format: BriefingFormat = BriefingFormat.EMAIL
    briefing_depth: int = 10
    is_pro: bool = False
    api_key: str = ""
    api_key_hash: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## Schema Changes

### 1. New Fields on `User`

Add after the existing `api_key_hash` field:

```python
# Stripe subscription
stripe_customer_id: str = ""          # Stripe Customer ID (cus_xxx), empty if never subscribed
stripe_subscription_id: str = ""      # Stripe Subscription ID (sub_xxx), empty if no active sub
pro_since: datetime | None = None     # When Pro was first activated
pro_until: datetime | None = None     # Grace period end (null = no grace period active)
```

**Field semantics:**

| Field | Set when | Cleared when |
|-------|----------|--------------|
| `stripe_customer_id` | First checkout session created | Never (reused for returning customers) |
| `stripe_subscription_id` | `checkout.session.completed` webhook | `customer.subscription.deleted` webhook |
| `is_pro` | `checkout.session.completed` webhook | Grace period expiry job |
| `pro_since` | `checkout.session.completed` webhook (first time only) | Never (historical record) |
| `pro_until` | `invoice.payment_failed` or `customer.subscription.deleted` | Cleared when `invoice.paid` (renewal success) |

### 2. New Table: `StripeEvent`

Idempotent webhook processing requires tracking which Stripe events have been
handled. Without this, a replayed or duplicated webhook would re-process.

```python
class StripeEvent(SQLModel, table=True):
    """Tracks processed Stripe webhook events for idempotent handling."""
    id: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(unique=True, index=True)   # Stripe event ID (evt_xxx)
    event_type: str = ""                               # e.g. "checkout.session.completed"
    user_id: int | None = Field(default=None, foreign_key="user.id")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

**Usage pattern in webhook handler:**

```python
existing = session.exec(
    select(StripeEvent).where(StripeEvent.event_id == event["id"])
).first()
if existing:
    return  # already processed — skip

# ... process event ...

session.add(StripeEvent(
    event_id=event["id"],
    event_type=event["type"],
    user_id=user.id,
))
session.commit()
```

### 3. New Enum: `SubscriptionStatus`

Optional, for future observability. Track in the User model if needed:

```python
class SubscriptionStatus(StrEnum):
    NONE = "none"           # never subscribed
    ACTIVE = "active"       # paying Pro
    GRACE = "grace"         # payment failed, within 7-day window
    CANCELLED = "cancelled" # user cancelled, may still be active until period end
    EXPIRED = "expired"     # grace period ended, downgraded to free
```

**Not stored in DB for v1** — derived from `is_pro`, `pro_until`, and
`stripe_subscription_id` at read time. Listed here for future reference.

---

## Alembic Migration

File: `alembic/versions/007_add_stripe_fields.py`

```python
"""Add Stripe subscription fields to User and StripeEvent table.

Revision ID: 007
Revises: 006
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"


def upgrade() -> None:
    # Add Stripe fields to User
    op.add_column("user", sa.Column("stripe_customer_id", sa.String(), server_default="", nullable=False))
    op.add_column("user", sa.Column("stripe_subscription_id", sa.String(), server_default="", nullable=False))
    op.add_column("user", sa.Column("pro_since", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("pro_until", sa.DateTime(), nullable=True))

    # Create StripeEvent table
    op.create_table(
        "stripeevent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(), nullable=False, unique=True),
        sa.Column("event_type", sa.String(), server_default="", nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stripeevent_event_id", "stripeevent", ["event_id"])


def downgrade() -> None:
    op.drop_table("stripeevent")
    op.drop_column("user", "pro_until")
    op.drop_column("user", "pro_since")
    op.drop_column("user", "stripe_subscription_id")
    op.drop_column("user", "stripe_customer_id")
```

**Migration safety:**
- All new `User` columns have defaults (`""` or `None`) — no data loss
- Existing users unaffected (`stripe_customer_id=""`, `pro_until=None`)
- `StripeEvent` is a brand new table — no conflicts
- Downgrade drops cleanly

---

## Config Changes (`src/prism/config.py`)

Add to `Settings` class after the existing `ntfy_topic` field:

```python
# Stripe (required for payment, optional for dev without payments)
stripe_secret_key: str = ""           # sk_test_... or sk_live_...
stripe_publishable_key: str = ""      # pk_test_... or pk_live_...
stripe_webhook_secret: str = ""       # whsec_...
stripe_price_id: str = ""             # price_... ($7/mo recurring)
grace_period_days: int = 7            # days before downgrade after payment failure
```

**Validation:** no startup crash if empty — Stripe endpoints return 503 with
"Stripe not configured" if `stripe_secret_key` is empty. This allows running
the pipeline without Stripe in development.

---

## Environment Variables

Added to `.env` / `.env.local.example`:

```env
# Stripe (leave empty to disable payment features)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
GRACE_PERIOD_DAYS=7
```

---

## API Response Schema Updates

Update `UserOut` in `routes.py` to expose subscription status to the frontend:

```python
class UserOut(BaseModel):
    id: int
    email: str
    name: str
    interests: str
    preferred_format: str
    briefing_depth: int
    is_pro: bool
    created_at: datetime
    # New fields
    pro_since: datetime | None
    pro_until: datetime | None
    has_stripe_subscription: bool   # derived: stripe_subscription_id != ""

    model_config = {"from_attributes": True}
```

**Important:** `stripe_customer_id` and `stripe_subscription_id` are NOT
exposed in the API response. They are internal Stripe references. The
frontend only sees `is_pro`, `pro_since`, `pro_until`, and
`has_stripe_subscription`.

Custom validator on `UserOut`:

```python
@model_validator(mode="before")
@classmethod
def derive_has_stripe(cls, data):
    if hasattr(data, "stripe_subscription_id"):
        data.has_stripe_subscription = bool(data.stripe_subscription_id)
    return data
```

---

## Stripe Product Setup (Manual, One-Time)

Run via Stripe Dashboard or CLI before deploying:

```bash
# Create product
stripe products create --name="Prism Pro" --description="Unlimited topics, audio briefings, API access"

# Create recurring price
stripe prices create \
  --product=prod_xxx \
  --unit-amount=700 \
  --currency=usd \
  --recurring[interval]=month

# Store the price_id (price_xxx) in STRIPE_PRICE_ID
```

**Test mode:** use `sk_test_*` / `pk_test_*` keys during development.
Production keys swapped via environment variables at deploy time.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Alembic migration applies cleanly | `alembic upgrade head` exits 0 on existing DB |
| 2 | Alembic downgrade works | `alembic downgrade 006` exits 0, fields removed |
| 3 | Existing users retain all data after migration | Query users, verify email/interests/is_pro unchanged |
| 4 | New User rows have empty Stripe fields by default | Create user via API, verify `stripe_customer_id=""` |
| 5 | StripeEvent table exists with unique index on event_id | Insert duplicate event_id, verify IntegrityError |
| 6 | Config loads Stripe keys from environment | Set `STRIPE_SECRET_KEY=test`, verify `settings.stripe_secret_key == "test"` |
| 7 | Config defaults to empty strings when Stripe vars unset | Unset all Stripe vars, verify no startup crash |
| 8 | UserOut response includes `pro_since`, `pro_until`, `has_stripe_subscription` | GET /users/{id}, verify new fields in JSON |
| 9 | UserOut does NOT expose `stripe_customer_id` or `stripe_subscription_id` | GET /users/{id}, verify fields absent |
| 10 | `grace_period_days` config defaults to 7 | Verify `settings.grace_period_days == 7` |

---

## Testing Strategy

- **Migration test:** apply 007, verify table schema, downgrade, verify clean
- **Model test:** create User with Stripe fields, verify defaults
- **Model test:** create StripeEvent, verify unique constraint on event_id
- **Config test:** Stripe settings load from env, default to empty
- **API test:** UserOut serialization includes derived `has_stripe_subscription`
- **Regression:** all existing User tests pass unchanged

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/models.py` | Add 4 fields to User, add StripeEvent table |
| `src/prism/config.py` | Add 5 Stripe/grace settings |
| `src/prism/api/routes.py` | Update UserOut with new fields + validator |
| `alembic/versions/007_add_stripe_fields.py` | New migration |
| `.env.example` | Add Stripe env vars |

---

## Dependencies (New)

```
stripe>=10.0     # Stripe Python SDK
```

Add to `pyproject.toml` under `[project.dependencies]`.
