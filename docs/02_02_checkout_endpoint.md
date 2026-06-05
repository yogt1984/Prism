# 02_02 — Checkout Session Endpoint

**Parent:** 02 Stripe Payment Integration
**Depends on:** 02_01 (schema + config)

---

## Objective

Implement the backend endpoint that creates a Stripe Checkout Session for
upgrading a free user to Pro. The session redirects the user to Stripe's
hosted payment page — no card data touches our servers.

---

## Endpoint Specification

### POST /users/{user_id}/checkout

**Authentication:** `X-API-Key` header (existing `require_api_key` dependency)
**Authorization:** user can only create checkout for their own account

**Request:** no body required (price comes from server config)

**Response (200):**
```json
{
  "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..."
}
```

**Error responses:**

| Status | Condition | Body |
|--------|-----------|------|
| 401 | Missing or invalid API key | `{"detail": "Missing API key"}` |
| 403 | API key belongs to different user | `{"detail": "Access denied: you can only access your own resources"}` |
| 409 | User is already Pro | `{"detail": "User is already a Pro subscriber"}` |
| 503 | Stripe not configured | `{"detail": "Payment processing is not configured"}` |
| 502 | Stripe API error | `{"detail": "Payment service temporarily unavailable"}` |

---

## Implementation

File: `src/prism/api/routes.py` (add to existing routes)

### Response Schema

```python
class CheckoutResponse(BaseModel):
    checkout_url: str
```

### Route Handler

```python
@router.post("/users/{user_id}/checkout", response_model=CheckoutResponse)
def create_checkout(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session for Pro upgrade."""
    # 1. Authorization — same pattern as existing user endpoints
    if auth_user.id != user_id:
        raise HTTPException(status_code=403,
            detail="Access denied: you can only access your own resources")

    # 2. Check Stripe is configured
    from prism.config import get_settings
    s = get_settings()
    if not s.stripe_secret_key or not s.stripe_price_id:
        raise HTTPException(status_code=503,
            detail="Payment processing is not configured")

    # 3. Load fresh user from DB
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # 4. Already Pro check
    if user.is_pro:
        raise HTTPException(status_code=409,
            detail="User is already a Pro subscriber")

    # 5. Create or reuse Stripe Customer
    import stripe
    stripe.api_key = s.stripe_secret_key

    try:
        if user.stripe_customer_id:
            customer_id = user.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"prism_user_id": str(user.id)},
            )
            customer_id = customer.id
            user.stripe_customer_id = customer_id
            session.add(user)
            session.commit()

        # 6. Create Checkout Session
        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": s.stripe_price_id, "quantity": 1}],
            success_url=f"{s.frontend_url}/settings?upgraded=true",
            cancel_url=f"{s.frontend_url}/settings?upgrade_cancelled=true",
            metadata={"prism_user_id": str(user.id)},
            subscription_data={
                "metadata": {"prism_user_id": str(user.id)},
            },
        )

    except stripe.StripeError as exc:
        raise HTTPException(status_code=502,
            detail="Payment service temporarily unavailable") from exc

    return CheckoutResponse(checkout_url=checkout_session.url)
```

---

## Config Addition

Add to `Settings` in `config.py` (alongside the Stripe keys from 02_01):

```python
frontend_url: str = "http://localhost:3000"   # base URL for redirect targets
```

This is used for `success_url` and `cancel_url` in Checkout Session creation.
In production, set to `https://yourdomain.com`.

---

## Stripe Customer Reuse

A user who previously subscribed (then cancelled) already has a
`stripe_customer_id`. Reusing it means:

- Their payment history is preserved in Stripe Dashboard
- Saved payment methods appear in the checkout form
- No duplicate Customer objects in Stripe

The check is simple: if `user.stripe_customer_id` is truthy, skip
`Customer.create()` and pass the existing ID directly.

---

## Stripe Checkout Session Parameters

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| `mode` | `"subscription"` | Recurring monthly billing |
| `line_items` | Single item: price_id × 1 | One subscription product |
| `customer` | Existing or new customer ID | Links payment to user |
| `success_url` | `/settings?upgraded=true` | User returns here after payment |
| `cancel_url` | `/settings?upgrade_cancelled=true` | User returns here if they cancel |
| `metadata.prism_user_id` | User's Prism ID | Used by webhook to find user |
| `subscription_data.metadata` | Same prism_user_id | Copied to Subscription object |

**Why metadata on both Session and Subscription:**
The `checkout.session.completed` webhook contains the session metadata.
Future subscription events (`invoice.paid`, etc.) contain the subscription
metadata. Setting both ensures we can find the Prism user from either.

---

## Frontend BFF Integration

The frontend calls this via the BFF proxy:

```
Browser → POST /api/bff/users/5/checkout
       → BFF attaches X-API-Key from session
       → FastAPI creates Stripe Checkout Session
       → Returns {checkout_url}
Browser → window.location.href = checkout_url
       → User completes payment on Stripe-hosted page
       → Stripe redirects to /settings?upgraded=true
```

No Stripe.js or client-side SDK needed — the entire payment form is hosted
by Stripe. This simplifies PCI compliance.

---

## Security Considerations

- **Price never from client:** `STRIPE_PRICE_ID` comes from server config.
  A tampered request body cannot change the price.
- **Customer creation is server-side:** no Stripe API key on the client.
- **Metadata is server-set:** `prism_user_id` in metadata cannot be spoofed
  by the client — it comes from the authenticated session.
- **Stripe key scoping:** use a restricted key with only `checkout.sessions`
  and `customers` write permissions if possible.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Free user gets valid checkout_url | Call endpoint, verify URL starts with `https://checkout.stripe.com` |
| 2 | Checkout URL opens Stripe payment page | Visit URL in browser, verify payment form renders |
| 3 | Already-Pro user gets 409 | Set `is_pro=True`, call endpoint, verify 409 response |
| 4 | Unconfigured Stripe returns 503 | Clear `STRIPE_SECRET_KEY`, call endpoint, verify 503 |
| 5 | stripe_customer_id persists after first checkout | Call endpoint, verify User row has `cus_xxx` |
| 6 | Returning customer reuses existing stripe_customer_id | Cancel subscription, call checkout again, verify same `cus_xxx` |
| 7 | Wrong user_id returns 403 | Call with different user's API key, verify 403 |
| 8 | Metadata contains prism_user_id | Check Stripe Dashboard, verify metadata on Session |
| 9 | success_url matches frontend_url config | Verify redirect URL uses configured domain |
| 10 | Stripe API error returns 502 (not 500) | Mock Stripe timeout, verify 502 response |

---

## Testing Strategy

### Unit Tests (mock Stripe SDK)

```python
def test_checkout_creates_session(mock_stripe, free_user, client):
    """Free user gets a checkout URL."""
    mock_stripe.checkout.Session.create.return_value = Mock(
        url="https://checkout.stripe.com/c/pay/cs_test_123"
    )
    res = client.post(f"/users/{free_user.id}/checkout",
                      headers={"X-API-Key": free_user_key})
    assert res.status_code == 200
    assert res.json()["checkout_url"].startswith("https://checkout.stripe.com")

def test_checkout_rejects_pro_user(pro_user, client):
    """Already-Pro user gets 409."""
    res = client.post(f"/users/{pro_user.id}/checkout",
                      headers={"X-API-Key": pro_user_key})
    assert res.status_code == 409

def test_checkout_rejects_wrong_user(free_user, other_user_key, client):
    """Cannot checkout for another user."""
    res = client.post(f"/users/{free_user.id}/checkout",
                      headers={"X-API-Key": other_user_key})
    assert res.status_code == 403

def test_checkout_returns_503_when_unconfigured(free_user, client, no_stripe_config):
    """503 when Stripe keys are empty."""
    res = client.post(f"/users/{free_user.id}/checkout",
                      headers={"X-API-Key": free_user_key})
    assert res.status_code == 503

def test_checkout_creates_customer_on_first_call(mock_stripe, free_user, client):
    """First checkout creates a Stripe Customer and stores ID."""
    mock_stripe.Customer.create.return_value = Mock(id="cus_test_123")
    client.post(f"/users/{free_user.id}/checkout",
                headers={"X-API-Key": free_user_key})
    assert free_user.stripe_customer_id == "cus_test_123"

def test_checkout_reuses_existing_customer(mock_stripe, returning_user, client):
    """Returning customer skips Customer.create."""
    client.post(f"/users/{returning_user.id}/checkout",
                headers={"X-API-Key": returning_user_key})
    mock_stripe.Customer.create.assert_not_called()
```

### Integration Test (Stripe test mode)

```python
def test_full_checkout_flow_stripe_test_mode(live_stripe, free_user, client):
    """End-to-end: create checkout session with real Stripe test keys."""
    res = client.post(f"/users/{free_user.id}/checkout",
                      headers={"X-API-Key": free_user_key})
    assert res.status_code == 200
    url = res.json()["checkout_url"]
    assert "checkout.stripe.com" in url
    # Verify session exists in Stripe
    session_id = url.split("/")[-1]
    session = stripe.checkout.Session.retrieve(session_id)
    assert session.metadata["prism_user_id"] == str(free_user.id)
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/api/routes.py` | Add `CheckoutResponse` schema + `POST /users/{id}/checkout` |
| `src/prism/config.py` | Add `frontend_url` setting |
| `tests/test_api_checkout.py` | New test file |
