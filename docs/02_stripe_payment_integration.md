# 02 — Stripe Payment Integration

**Priority:** 2 (Revenue)
**Depends on:** Web Frontend (Priority 1) for checkout UI
**Unlocks:** Subscription revenue, Pro tier activation

---

## Objective

Enable real payment processing for the Pro tier ($7/mo). Tier enforcement
already exists in P_AI (story limits), W_AI (format gating), and the API
(auth middleware). This task wires up Stripe to flip `User.is_pro`.

---

## Current Tier Enforcement (Already Implemented)

| Component | Free Tier                  | Pro Tier                     |
|-----------|----------------------------|------------------------------|
| P_AI      | 1 interest category, max 10 stories | All categories, max 25 stories |
| W_AI      | Email format only          | Email, JSON feed, audio script |
| API       | 60 req/min rate limit      | 120 req/min rate limit       |

**No code changes needed in agents or API tier logic.** Only `User.is_pro`
needs to toggle.

---

## Architecture

```
Browser                    Next.js BFF              Stripe              FastAPI
   |                          |                       |                    |
   |-- Click "Upgrade" ------>|                       |                    |
   |                          |-- Create Checkout --->|                    |
   |<-- Redirect to Stripe ---|                       |                    |
   |-- Complete payment ----->|                       |                    |
   |                          |                       |-- Webhook -------->|
   |                          |                       |   (checkout.done)  |
   |                          |                       |                    |-- Set is_pro=True
   |<-- Redirect to /settings (success) --------------|                    |
```

---

## Implementation Tasks

### 1. Stripe Configuration

- Create Stripe product: "Prism Pro" with $7/mo recurring price
- Store in environment config:
  - `STRIPE_SECRET_KEY` — server-side API calls
  - `STRIPE_PUBLISHABLE_KEY` — client-side checkout
  - `STRIPE_WEBHOOK_SECRET` — webhook signature verification
  - `STRIPE_PRICE_ID` — the $7/mo price object ID

### 2. New Database Fields

Add to `User` model:

```
stripe_customer_id (str | None)    — Stripe Customer ID (cus_xxx)
stripe_subscription_id (str | None) — Stripe Subscription ID (sub_xxx)
pro_since (datetime | None)        — When Pro was activated
pro_until (datetime | None)        — Grace period end after cancellation
```

Alembic migration: `007_add_stripe_fields.py`

### 3. Backend Endpoints

**POST /users/{user_id}/checkout**
- Auth: requires valid API key for this user
- Creates Stripe Checkout Session in `subscription` mode
- Sets `success_url` and `cancel_url` back to frontend
- Stores `stripe_customer_id` on User if first time
- Returns: `{checkout_url: str}`

**POST /webhooks/stripe**
- No API-key auth (Stripe signature verification instead)
- Handles events:
  - `checkout.session.completed` → set `is_pro=True`, store `stripe_subscription_id`, set `pro_since`
  - `invoice.paid` → renewal confirmation (extend `pro_until`)
  - `invoice.payment_failed` → set `pro_until` = now + 7 days (grace period)
  - `customer.subscription.deleted` → set `is_pro=False` after grace period
- Idempotent: use Stripe event ID to prevent double-processing

**POST /users/{user_id}/portal**
- Auth: requires valid API key, user must be Pro
- Creates Stripe Customer Portal session (manage/cancel subscription)
- Returns: `{portal_url: str}`

### 4. Frontend Pages

**Upgrade CTA (Settings page)**
- "Upgrade to Pro — $7/month" button
- Calls `POST /users/{id}/checkout` → redirects to `checkout_url`
- After payment: Stripe redirects to `/settings?upgraded=true`

**Success state**
- Settings page shows "Pro" badge when `is_pro=True`
- Locked features (audio format, extra categories) become active

**Manage subscription**
- "Manage Subscription" link for Pro users
- Calls `POST /users/{id}/portal` → redirects to Stripe portal
- Users can cancel, update payment method, view invoices

### 5. Grace Period Logic

When payment fails or subscription is cancelled:

- Set `pro_until` = current time + 7 days
- During grace period: `is_pro` stays `True`
- Background job (daily): check users where `pro_until < now()` → set `is_pro=False`
- Send ntfy alert when grace period starts (existing alerts.py)

---

## Security Requirements

- **Webhook verification:** Every Stripe webhook request must be verified using
  `stripe.Webhook.construct_event()` with the webhook secret
- **No client-side price:** Price ID comes from server config, never from the browser
- **Idempotent processing:** Store processed event IDs to prevent duplicate activations
- **PCI compliance:** No card data touches our servers (Stripe Checkout handles it)

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Free user can initiate checkout flow | Click upgrade, verify redirect to Stripe Checkout |
| 2 | Successful payment activates Pro tier | Complete test payment, verify `is_pro=True` in DB |
| 3 | Pro user sees unlocked features immediately | After upgrade, audio format selectable in settings |
| 4 | P_AI respects new Pro status on next briefing | Trigger briefing cycle, verify all categories included |
| 5 | Webhook processes `checkout.session.completed` | Send test webhook via Stripe CLI, verify DB update |
| 6 | Webhook ignores duplicate events | Send same event twice, verify single DB update |
| 7 | Failed payment sets 7-day grace period | Simulate failed invoice, verify `pro_until` set |
| 8 | Expired grace period downgrades to free | Advance time past `pro_until`, run daily job, verify `is_pro=False` |
| 9 | User can cancel via Stripe portal | Open portal, cancel, verify subscription state |
| 10 | Webhook endpoint rejects unsigned requests | Send request without Stripe signature, verify 400 |
| 11 | Stripe keys are never exposed to client | Inspect browser network tab, only publishable key visible |

---

## Testing Strategy

- **Stripe Test Mode:** All development uses Stripe test keys (`sk_test_*`)
- **Stripe CLI:** `stripe listen --forward-to localhost:8000/webhooks/stripe`
  for local webhook testing
- **Test cards:** `4242424242424242` (success), `4000000000000341` (decline)
- **Unit tests:** Mock Stripe SDK, test webhook handler logic in isolation
- **Integration test:** Full flow from checkout creation to Pro activation
- **CI:** Stripe test keys in GitHub Actions secrets

---

## Environment Variables (New)

```
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_ID=price_...
```

Added to `config.py` as optional fields (empty string defaults).
