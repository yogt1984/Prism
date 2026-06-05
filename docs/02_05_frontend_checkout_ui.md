# 02_05 — Frontend Checkout & Subscription UI

**Parent:** 02 Stripe Payment Integration
**Depends on:** 02_02 (checkout endpoint), 02_04 (portal endpoint), 01_06 (settings page)

---

## Objective

Wire the Stripe checkout and portal endpoints into the frontend settings page.
Users upgrade via a button that redirects to Stripe's hosted checkout, and
manage their subscription via Stripe's Customer Portal. No Stripe.js needed —
all payment UI is Stripe-hosted.

---

## Affected Pages

Only `/settings` is modified. No new pages are created.

---

## Component Changes to Settings Page (`01_06`)

### SubscriptionSection — Before (01_06 placeholder)

```
<UpgradeButton disabled />     // was disabled, labeled "Coming soon"
<ManageButton disabled />      // was disabled
```

### SubscriptionSection — After (wired)

```
<SubscriptionSection>
  <SectionHeading text="Subscription" />

  <CurrentPlanCard>
    <PlanBadge tier={user.isPro ? "Pro" : "Free"} />
    <PlanPrice visible={user.isPro} text="$7/month" />
    <ProSinceDate visible={user.proSince} text={formatDate(user.proSince)} />
    <GracePeriodWarning visible={user.proUntil && isFuture(user.proUntil)}>
      <WarningIcon />
      <Text text="Payment issue — Pro access until {formatDate(user.proUntil)}" />
      <UpdatePaymentButton onClick={openPortal} />
    </GracePeriodWarning>
  </CurrentPlanCard>

  <UpgradeSection visible={!user.isPro}>
    <UpgradeCard>
      <Heading text="Upgrade to Pro" />
      <Price text="$7" period="/month" />
      <FeatureList>
        <Feature text="All 8 topic categories" />
        <Feature text="Up to 25 stories per briefing" />
        <Feature text="Audio briefings" />
        <Feature text="JSON API access" />
        <Feature text="Unlimited keyword tracking" />
      </FeatureList>
      <UpgradeButton
        text="Upgrade Now"
        onClick={handleUpgrade}
        loading={isCheckoutLoading}
      />
    </UpgradeCard>
  </UpgradeSection>

  <ManageSection visible={user.isPro}>
    <ManageButton
      text="Manage Subscription"
      onClick={handleManage}
      loading={isPortalLoading}
    />
    <ManageDescription text="Update payment method, view invoices, or cancel" />
  </ManageSection>

  <FeatureComparison>
    // unchanged from 01_06
  </FeatureComparison>
</SubscriptionSection>
```

---

## API Calls

### Initiate Checkout (Upgrade)

```
POST /api/bff/users/{userId}/checkout

Response (200):
{ "checkout_url": "https://checkout.stripe.com/c/pay/cs_test_..." }

Errors:
  409: { "detail": "User is already a Pro subscriber" }
  503: { "detail": "Payment processing is not configured" }
  502: { "detail": "Payment service temporarily unavailable" }
```

### Open Customer Portal (Manage)

```
POST /api/bff/users/{userId}/portal

Response (200):
{ "portal_url": "https://billing.stripe.com/p/session/..." }

Errors:
  409: { "detail": "No subscription to manage" }
  503: { "detail": "Payment processing is not configured" }
  502: { "detail": "Billing portal temporarily unavailable" }
```

### Refresh User State (after return from Stripe)

```
GET /api/bff/users/{userId}

Response: UserOut (with updated is_pro, pro_since, pro_until, has_stripe_subscription)
```

---

## Checkout Flow UX

### Step-by-step sequence:

```
1. User clicks "Upgrade Now"
   → Button shows spinner, text changes to "Redirecting to payment..."
   → POST /api/bff/users/{id}/checkout

2. Redirect to Stripe Checkout
   → window.location.href = checkout_url
   → User is on Stripe's hosted payment page

3a. User completes payment
   → Stripe redirects to /settings?upgraded=true
   → Settings page detects query param
   → Refetch user profile (may take 1-3s for webhook to process)
   → Show success state

3b. User cancels / closes Stripe page
   → Stripe redirects to /settings?upgrade_cancelled=true
   → Settings page shows: "Upgrade cancelled. You can try again anytime."
   → Auto-dismiss after 5 seconds
```

### Post-Checkout Polling

The webhook that sets `is_pro=True` is asynchronous — it may arrive 1-5
seconds after the user returns to `/settings`. Handle this with a polling
strategy:

```typescript
function usePostCheckoutPolling(userId: number, upgraded: boolean) {
  const queryClient = useQueryClient()
  const [attempts, setAttempts] = useState(0)

  useEffect(() => {
    if (!upgraded || attempts >= 10) return

    const timer = setTimeout(async () => {
      await queryClient.invalidateQueries(["users", userId])
      const user = queryClient.getQueryData<User>(["users", userId])
      if (user?.is_pro) {
        // Success — webhook processed
        return
      }
      setAttempts(a => a + 1)  // retry
    }, 1000)  // poll every 1 second

    return () => clearTimeout(timer)
  }, [upgraded, attempts])

  return { isPolling: upgraded && attempts < 10 && !user?.is_pro }
}
```

**Polling behavior:**
- Poll `GET /users/{id}` every 1 second for up to 10 attempts
- Stop when `is_pro=True` (webhook processed) or after 10s (timeout)
- If timeout: show "Payment received. Your Pro features will activate shortly."

---

## Success State

When `/settings?upgraded=true` and user is confirmed Pro:

```
<SuccessBanner>
  <CheckCircleIcon className="text-green-500" />
  <Heading text="Welcome to Prism Pro!" />
  <Text text="All Pro features are now active." />
  <DismissButton />
</SuccessBanner>
```

- Auto-dismiss after 8 seconds
- Green background (`bg-green-50 border-green-200`)
- Confetti animation (optional — CSS keyframes, no library)

**Immediate UI changes after upgrade:**
- Plan badge switches from "Free" to "Pro"
- Audio format radio becomes enabled (01_06)
- Depth slider max changes from 10 to 25 (01_06)
- Interest grid free-tier notice disappears (01_06)
- "Upgrade" section replaced by "Manage Subscription"

---

## Grace Period Warning

When `user.pro_until` is set and in the future, the user is in a grace period
(payment failed but still has Pro access temporarily).

```
<GracePeriodWarning>
  <AlertTriangleIcon className="text-amber-500" />
  <WarningText>
    There's an issue with your payment. Pro access continues until
    {formatDate(user.proUntil)}.
  </WarningText>
  <UpdatePaymentButton
    text="Update Payment Method"
    onClick={handleManage}
    variant="primary"
  />
</GracePeriodWarning>
```

- Yellow/amber background (`bg-amber-50 border-amber-200`)
- Persistent — does not auto-dismiss
- "Update Payment Method" opens Stripe Customer Portal

---

## Cancelled State

When `user.is_pro` is `False` and `user.pro_until` is in the past:

```
<ResubscribeNotice>
  <Text text="Your Pro subscription ended on {formatDate(user.proUntil)}." />
  <UpgradeButton text="Resubscribe" onClick={handleUpgrade} />
</ResubscribeNotice>
```

---

## Error Handling

| Scenario | UX |
|----------|-----|
| Checkout 409 (already Pro) | Toast: "You're already a Pro subscriber!" + refetch user |
| Checkout 503 (not configured) | Toast: "Payments are temporarily unavailable. Try again later." |
| Checkout 502 (Stripe down) | Toast: "Payment service is temporarily unavailable." |
| Portal 409 (no customer) | Toast: "No active subscription to manage." |
| Portal 502 (Stripe down) | Toast: "Billing portal temporarily unavailable." |
| Network error | Toast: "Connection error — check your internet." |
| Polling timeout (10s) | Inline message: "Payment received. Pro features will activate shortly." |

---

## Updated TypeScript Types

Add to `lib/types.ts` (from 01_08):

```typescript
export interface User {
  // ... existing fields ...
  pro_since: string | null
  pro_until: string | null
  has_stripe_subscription: boolean
}

export interface CheckoutResponse {
  checkout_url: string
}

export interface PortalResponse {
  portal_url: string
}
```

Add to `lib/api.ts`:

```typescript
export const api = {
  // ... existing ...
  subscription: {
    checkout: (userId: number) =>
      apiFetch<CheckoutResponse>(`/users/${userId}/checkout`, { method: "POST" }),
    portal: (userId: number) =>
      apiFetch<PortalResponse>(`/users/${userId}/portal`, { method: "POST" }),
  },
}
```

---

## React Query Hooks

File: `lib/hooks/useSubscription.ts`

```typescript
import { useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useCheckout(userId: number) {
  return useMutation({
    mutationFn: () => api.subscription.checkout(userId),
    onSuccess: (data) => {
      window.location.href = data.checkout_url
    },
  })
}

export function usePortal(userId: number) {
  return useMutation({
    mutationFn: () => api.subscription.portal(userId),
    onSuccess: (data) => {
      window.location.href = data.portal_url
    },
  })
}
```

---

## Mobile Breakpoints

| Breakpoint | Layout |
|------------|--------|
| >= 768px (md) | UpgradeCard as card with feature list side by side. ManageButton inline with description. |
| < 768px (sm) | UpgradeCard full-width, feature list stacked. ManageButton full-width. GracePeriodWarning full-width with stacked text + button. |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | "Upgrade Now" button redirects to Stripe Checkout | Click button, verify Stripe page opens |
| 2 | Successful payment redirects to `/settings?upgraded=true` | Complete test payment, verify redirect |
| 3 | Success banner appears after upgrade | Verify green banner with "Welcome to Prism Pro!" |
| 4 | Pro features unlock immediately in settings UI | Verify audio format enabled, slider max=25 |
| 5 | Plan badge changes from "Free" to "Pro" | Visual check |
| 6 | "Manage Subscription" button opens Stripe Portal | Click, verify Stripe portal page |
| 7 | Grace period warning shows when `pro_until` is set | Set grace period, reload, verify amber banner |
| 8 | "Update Payment Method" in grace warning opens portal | Click, verify portal redirect |
| 9 | Cancelled state shows resubscribe option | Cancel sub, wait for expiry, verify resubscribe UI |
| 10 | Polling detects Pro activation within 10 seconds | Complete payment, time the transition |
| 11 | Polling timeout shows fallback message | Block webhook, verify timeout message after 10s |
| 12 | Already-Pro 409 shows toast | Set `is_pro=True`, click upgrade, verify toast |
| 13 | Mobile layout is usable at 375px | Resize, verify all elements accessible |

---

## Testing Strategy

### Unit Tests

- `UpgradeCard` renders feature list and button
- `GracePeriodWarning` shows when `proUntil` is future date
- `GracePeriodWarning` hidden when `proUntil` is null
- `usePostCheckoutPolling` polls and stops on `is_pro=True`
- `usePostCheckoutPolling` stops after 10 attempts
- Success banner auto-dismisses after 8 seconds

### Integration Tests (MSW)

- Mock checkout endpoint → verify redirect called with URL
- Mock portal endpoint → verify redirect called with URL
- Mock user endpoint returning `is_pro=true` on 3rd poll → verify polling stops

### E2E (Playwright)

- Full flow: login as free → click upgrade → complete Stripe test payment
  → verify return to settings → verify Pro badge
  (requires Stripe test mode + test card `4242424242424242`)

---

## Files Changed

| File | Change |
|------|--------|
| `frontend/app/settings/page.tsx` | Wire SubscriptionSection with checkout + portal |
| `frontend/lib/hooks/useSubscription.ts` | New: `useCheckout`, `usePortal` hooks |
| `frontend/lib/types.ts` | Add `CheckoutResponse`, `PortalResponse`, update `User` |
| `frontend/lib/api.ts` | Add `subscription.checkout()`, `subscription.portal()` |
| `frontend/components/subscription/UpgradeCard.tsx` | New component |
| `frontend/components/subscription/GracePeriodWarning.tsx` | New component |
| `frontend/components/subscription/SuccessBanner.tsx` | New component |
| `frontend/__tests__/components/subscription/` | New test files |
