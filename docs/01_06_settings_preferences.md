# 01_06 — Settings & User Preferences

**Parent:** 01 Web Frontend
**Depends on:** 01_01 (auth, session management)

---

## Objective

Build the settings page where users manage their profile, interest categories,
briefing format/depth preferences, and subscription tier. All fields map
directly to `PATCH /users/{id}` with existing backend validation.

---

## Route

`/settings` — protected.

---

## Component Tree

```
<SettingsPage>
  <PageHeader>
    <Heading text="Settings" />
  </PageHeader>

  <SettingsSections>
    <ProfileSection>
      <SectionHeading text="Profile" />
      <FormField label="Email" value={user.email} disabled />
      <FormField label="Name">
        <TextInput
          value={name}
          onChange={setName}
          placeholder="Your name"
          maxLength={100}
        />
      </FormField>
      <SaveButton onClick={saveName} disabled={name === user.name} />
    </ProfileSection>

    <InterestsSection>
      <SectionHeading text="Interests" />
      <SectionDescription text="Select topics for your briefings" />
      <InterestGrid>
        <InterestToggle category="finance" icon={DollarSign} />
        <InterestToggle category="politics" icon={Landmark} />
        <InterestToggle category="technology" icon={Cpu} />
        <InterestToggle category="sports" icon={Trophy} />
        <InterestToggle category="culture" icon={Palette} />
        <InterestToggle category="science" icon={Flask} />
        <InterestToggle category="health" icon={Heart} />
        <InterestToggle category="world" icon={Globe} />
      </InterestGrid>
      <TierNotice visible={!user.isPro}>
        <LockIcon />
        <Text text="Free tier: only your first selected category is used" />
      </TierNotice>
      <SaveButton onClick={saveInterests} disabled={!interestsChanged} />
    </InterestsSection>

    <BriefingPreferencesSection>
      <SectionHeading text="Briefing Preferences" />

      <FormatSelector>
        <SectionLabel text="Delivery Format" />
        <RadioGroup value={format} onChange={setFormat}>
          <RadioOption value="email" label="Email Newsletter" enabled />
          <RadioOption value="json_feed" label="JSON Feed (API)"
            enabled={user.isPro}
            lockedText="Pro only" />
          <RadioOption value="audio_script" label="Audio Briefing"
            enabled={user.isPro}
            lockedText="Pro only — coming soon" />
        </RadioGroup>
      </FormatSelector>

      <DepthSlider>
        <SectionLabel text="Stories per briefing" />
        <Slider
          min={1}
          max={user.isPro ? 25 : 10}
          value={depth}
          onChange={setDepth}
          step={1}
        />
        <SliderValue text={`${depth} stories`} />
        <TierNotice visible={!user.isPro}>
          <Text text="Free tier: max 10 stories. Upgrade for up to 25." />
        </TierNotice>
      </DepthSlider>

      <SaveButton onClick={savePreferences} disabled={!prefsChanged} />
    </BriefingPreferencesSection>

    <SubscriptionSection>
      <SectionHeading text="Subscription" />
      <CurrentPlan>
        <PlanBadge tier={user.isPro ? "Pro" : "Free"} />
        <PlanDescription text={planDescriptionText} />
      </CurrentPlan>
      <UpgradeButton visible={!user.isPro}
        text="Upgrade to Pro — $7/month"
        onClick={navigateToCheckout}
        disabled />                                // enabled in Priority 2
      <ManageButton visible={user.isPro}
        text="Manage Subscription"
        onClick={navigateToPortal}
        disabled />                                // enabled in Priority 2
      <FeatureComparison>
        <ComparisonRow feature="Topics" free="1" pro="All 8" />
        <ComparisonRow feature="Stories/briefing" free="10" pro="25" />
        <ComparisonRow feature="Formats" free="Email" pro="Email, JSON, Audio" />
        <ComparisonRow feature="API Access" free="No" pro="Yes" />
      </FeatureComparison>
    </SubscriptionSection>

    <ApiKeySection visible={user.isPro}>
      <SectionHeading text="API Key" />
      <SectionDescription text="Use this key to access the Prism API directly" />
      <ApiKeyDisplay>
        <MaskedKey text="prism_****...****" />
        <RevealButton onClick={toggleReveal} />
        <CopyButton onClick={copyToClipboard} />
        <RegenerateButton onClick={confirmRegenerate} />
      </ApiKeyDisplay>
      <Warning text="Regenerating will invalidate your current key immediately" />
    </ApiKeySection>

    <DangerZone>
      <SectionHeading text="Danger Zone" color="red" />
      <DeleteAccountButton onClick={confirmDelete} />
    </DangerZone>
  </SettingsSections>
</SettingsPage>
```

---

## API Calls

### Load User Profile

```
GET /api/bff/users/{userId}

Response: UserOut
{
  id: 5,
  email: "user@example.com",
  name: "Jane",
  interests: "finance,technology",
  preferred_format: "email",
  briefing_depth: 10,
  is_pro: false,
  created_at: "2026-05-15T10:00:00Z"
}
```

React Query key: `["users", userId]`
Stale time: 10 minutes (rarely changes except when user edits)

### Update Profile

Each section saves independently. All use the same endpoint:

```
PATCH /api/bff/users/{userId}
Body: { name: "Jane Doe" }                    // name only
Body: { interests: "finance,technology,health" } // interests only
Body: { preferred_format: "json_feed", briefing_depth: 15 } // prefs only

Response: UserOut (updated)

Errors:
  422: { detail: "Invalid interest: 'invalid'" }
  422: { detail: "Invalid format: 'unknown'" }
  422: { detail: "briefing_depth must be between 1 and 25" }
  403: { detail: "API access requires a Pro subscription" }
```

Mutation on success: update React Query cache for `["users", userId]`, show
toast "Settings saved". Also update NextAuth session if `interests` or
`is_pro` changed (call `update()` from `useSession`).

### Load Config (for tier limits)

```
GET /api/bff/config

Response: ConfigResponse
{
  categories: ["finance", "politics", "technology", "sports", "culture", "science", "health", "world"],
  tiers: {
    free_categories: 1,
    pro_categories: 8,
    free_max_stories: 10,
    pro_max_stories: 25,
    free_formats: ["email"],
    pro_formats: ["email", "json_feed", "audio_script"]
  },
  ...
}
```

React Query key: `["config"]`
Stale time: 60 minutes (almost never changes)

---

## Form State Management

Each section manages its own local form state independently using `useState`.
Save buttons are disabled until the local state differs from the server state.

```typescript
function InterestsSection({ user }: { user: UserOut }) {
  const [selected, setSelected] = useState<Set<string>>(
    new Set(user.interests.split(",").filter(Boolean))
  )
  const serverSet = new Set(user.interests.split(",").filter(Boolean))
  const changed = !setsEqual(selected, serverSet)

  function toggle(category: string) {
    const next = new Set(selected)
    next.has(category) ? next.delete(category) : next.add(category)
    setSelected(next)
  }

  async function save() {
    await updateUser({ interests: [...selected].join(",") })
  }

  return (/* ... */)
}
```

**No global form library needed.** Each section is a simple controlled form
with 1-2 fields.

---

## InterestToggle Component

Toggleable pill/card for each of the 8 categories.

```typescript
interface InterestToggleProps {
  category: string
  icon: LucideIcon
  selected: boolean
  onToggle: () => void
  disabled?: boolean  // true for free-tier categories beyond first
}
```

**Visual states:**

| State | Style |
|-------|-------|
| Selected | `bg-blue-50 border-blue-500 text-blue-700` + check icon |
| Unselected | `bg-white border-gray-200 text-gray-600` |
| Disabled (free tier, beyond 1st) | `bg-gray-50 border-gray-100 text-gray-400 opacity-50 cursor-not-allowed` |

Size: `px-4 py-3` with icon (20px) + category name.
Grid: `grid-cols-4` on desktop, `grid-cols-2` on mobile.

**Free tier logic:** user can select multiple interests (stored in DB), but
P_AI only uses the first one. Show all as selectable but display notice.

---

## DepthSlider Component

```typescript
interface DepthSliderProps {
  value: number
  onChange: (n: number) => void
  min: number       // always 1
  max: number       // 10 (free) or 25 (pro)
}
```

**Implementation:** native `<input type="range">` styled with Tailwind.
Current value shown as number beside the slider.
Tick marks at 1, 5, 10, 15, 20, 25 (Pro shows all, free shows up to 10).

---

## Subscription Section — Feature Comparison Table

Static comparison table. No API call.

```
┌─────────────────────┬────────────┬────────────┐
│ Feature             │ Free       │ Pro ($7/mo)│
├─────────────────────┼────────────┼────────────┤
│ Topics              │ 1          │ All 8      │
│ Stories/briefing    │ Up to 10   │ Up to 25   │
│ Formats             │ Email      │ All 3      │
│ API Access          │ ✗          │ ✓          │
│ Perception Tracking │ 3 keywords │ Unlimited  │
│ Audio Briefings     │ ✗          │ ✓          │
└─────────────────────┴────────────┴────────────┘
```

Upgrade button: disabled with tooltip "Coming soon" until Priority 2 (Stripe).
Manage button: hidden until user is Pro.

---

## API Key Section

Only visible to Pro users.

- Key is stored as `api_key_hash` (SHA-256) in the backend — the raw key
  was only shown once at creation time
- **Reveal:** not possible for existing keys (hash is one-way)
- **Regenerate:** creates new key, returns raw key once, stores new hash
  - Show confirmation dialog: "This will invalidate your current key"
  - On confirm: call backend endpoint (needs new endpoint or use existing flow)
  - Show raw key in copyable field with warning "Save this — it won't be shown again"

**Note:** The current API doesn't have a dedicated key regeneration endpoint.
This will need a `POST /users/{id}/api-key` endpoint added to the backend.

---

## UI States

### Loading
- Full page skeleton: section headings visible, form fields as pulsing rectangles

### Error

| Scenario | Display |
|----------|---------|
| User fetch fails | "Could not load settings" + retry button |
| Save returns 422 | Inline red text below the invalid field with API error detail |
| Save returns 403 | Toast: "This action requires a Pro subscription" |
| Save network error | Toast: "Could not save — check your connection" |

---

## Mobile Breakpoints

| Breakpoint | Layout |
|------------|--------|
| >= 768px (md) | `max-w-2xl` centered, InterestGrid 4 columns, comparison table full |
| < 768px (sm) | Full width `px-4`, InterestGrid 2 columns, comparison table scrollable, sections separated by `border-b` |

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Profile shows correct email and name | Compare with `GET /users/{id}` |
| 2 | Name change persists after save + reload | Edit name, save, reload, verify |
| 3 | Interest toggles reflect current interests | Compare checked items with `interests` field |
| 4 | Interest change saves correct comma-separated string | Toggle 2 categories, save, verify PATCH body |
| 5 | Free tier notice shows for non-Pro users | Login as free, verify lock icon + notice |
| 6 | Format radio disables Pro-only options for free users | Verify json_feed and audio_script are grayed |
| 7 | Depth slider respects tier max (10 free, 25 pro) | Verify slider max matches tier |
| 8 | Invalid interest returns inline error | Mock 422, verify red text below field |
| 9 | Save button disabled when no changes made | Load page, verify button is disabled |
| 10 | Feature comparison table renders all rows | Count 6 feature rows |
| 11 | API key section hidden for free users | Login as free, verify section absent from DOM |
| 12 | Settings persist across sessions | Edit, logout, login, verify same values |

---

## Testing Strategy

- **Unit:** `InterestToggle` renders selected/unselected/disabled states
- **Unit:** `DepthSlider` clamps value to min/max
- **Unit:** save button disabled logic (deep equality check)
- **Unit:** PATCH body construction from form state
- **Integration (MSW):** full page render, edit interests, mock save, verify toast
- **E2E:** change interests + format + depth → save → reload → verify persistence
