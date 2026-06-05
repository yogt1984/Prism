# 01 — Web Frontend

**Priority:** 1 (Foundation)
**Depends on:** Existing REST API (30+ endpoints, fully operational)
**Unlocks:** Stripe integration, TTS playback, public launch

---

## Objective

Build a user-facing web application that exposes Prism's capabilities to
non-technical users. The backend API is complete — this task bridges it to a
browser-based experience.

---

## Recommended Stack

| Layer        | Technology          | Rationale                                    |
|--------------|---------------------|----------------------------------------------|
| Framework    | Next.js 14+ (App Router) | SSR for SEO, API routes for BFF pattern |
| Styling      | Tailwind CSS        | Rapid iteration, consistent design system    |
| State        | React Query (TanStack) | Server state caching, auto-refetch        |
| Auth         | NextAuth.js         | Email magic-link flow, session management    |
| Charts       | Recharts or Tremor  | Perception pressure time-series visuals      |
| Deployment   | Docker (alongside API) | Single-host deployment on existing infra  |

---

## Pages & Components

### 1. Landing / Marketing Page (`/`)

- Product pitch: "Multi-perspective news briefings that make bias visible"
- Feature highlights: perspectives, resonance scores, perception tracking
- CTA: Sign up (free tier) or upgrade to Pro
- No authentication required

### 2. Auth Flow (`/login`, `/signup`)

- **Signup:** email + interest selection (checkboxes for 8 categories)
  - Calls `POST /users` with `{email, interests}`
  - Sends magic-link email for verification
- **Login:** email magic-link (no passwords)
  - NextAuth.js email provider
- **Session:** JWT stored in httpOnly cookie, refresh on expiry

### 3. Dashboard (`/dashboard`) — Authenticated

- **Today's briefing** card: rendered HTML from `content_html` field
  - Fetches `GET /users/{id}/briefings?limit=1`
  - Fallback: "No briefing yet — check back after 7am UTC"
- **Top stories by resonance**: horizontal card row
  - Fetches `GET /stories?sort=resonance&limit=5`
  - Each card shows headline, resonance score badge, category pill
- **Tracked keywords** sidebar: perception pressure sparklines
  - Fetches `GET /keywords?active=true` then per-keyword history
- **Quick actions:** trigger on-demand briefing, add keyword

### 4. Story Detail (`/stories/[id]`)

- Headline + neutral summary from `StoryCluster.summary`
- **Perspective cards** (side-by-side or tabbed):
  - Source name + bias label badge (left/center/right color-coded)
  - Perspective summary text
  - Sentiment bar (-1.0 to +1.0 visual scale)
  - Key claims as bullet list with source attribution links
- **Resonance panel:** score, momentum arrow, peak, source count
  - Fetches `GET /stories/{id}/resonance`
- **Article sources** list: links to original articles with source trust score
- **Engagement buttons:** save / skip (calls `POST /engagements`)

### 5. Briefing Archive (`/briefings`)

- Paginated list of past briefings
  - Fetches `GET /users/{id}/briefings?limit=20&offset=N`
- Each entry: date, story count, format badge
- Click to expand full briefing content
- Pro badge on audio-format briefings

### 6. Perception Dashboard (`/perception`)

- **Keyword list** with current perception value + momentum indicator
- **Time-series chart** per keyword: perception pressure over time
  - X-axis: time, Y-axis: perception (-1.0 to +1.0)
  - Overlaid: salience (bar) + valence (line)
  - Fetches `GET /keywords/{id}/perception/history?limit=100`
- **Add keyword** form: keyword, aliases, category
  - Calls `POST /keywords`
- **Remove keyword:** deactivate button → `DELETE /keywords/{id}`

### 7. Settings (`/settings`)

- **Profile:** name, email (read-only)
- **Interests:** category toggle grid (8 categories)
  - Calls `PATCH /users/{id}` with updated interests
- **Briefing preferences:**
  - Format: email / json / audio (audio Pro-only, grayed for free)
  - Depth: slider 1-25 stories
  - Calls `PATCH /users/{id}`
- **Subscription tier:** current plan + upgrade CTA (wired in Priority 2)
- **API key:** reveal/regenerate for Pro users

### 8. Source Explorer (`/sources`)

- Table of all active sources
  - Fetches `GET /sources?active=true`
- Columns: name, URL, trust score (progress bar), bias label (color badge)
- Sort by trust score or bias label
- Click to filter stories from that source

---

## API Integration Layer (BFF)

Next.js API routes act as a Backend-For-Frontend to:

- Attach the user's API key from session to `X-API-Key` header
- Translate between session-based auth (browser) and API-key auth (backend)
- Cache frequently-read data (sources list, keyword list) with SWR/stale-while-revalidate

```
Browser → Next.js API route → FastAPI backend
         (session → API key)
```

---

## Responsive Design

- **Desktop:** multi-column dashboard, side-by-side perspectives
- **Tablet:** stacked cards, collapsible sidebar
- **Mobile:** single-column, bottom nav, swipeable perspective cards

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | User can sign up with email and select interests | Signup flow creates user via `POST /users`, verify in DB |
| 2 | User can log in via magic link and see dashboard | Session persists across page reloads |
| 3 | Dashboard shows latest briefing content | Compare rendered HTML with `content_html` from API |
| 4 | Story detail shows all perspectives side-by-side | Verify perspective count matches `GET /stories/{id}` |
| 5 | Bias labels are color-coded (left=blue, right=red, center=gray) | Visual inspection across 5+ stories |
| 6 | Resonance scores display with momentum arrow | Compare values with `GET /stories/{id}/resonance` |
| 7 | Perception chart renders time-series for tracked keywords | Add keyword, wait for scan cycle, verify chart populates |
| 8 | Engagement actions (save/skip) are recorded | Click save, verify via `POST /engagements` in DB |
| 9 | Free tier users see Pro features as locked/grayed | Login as free user, confirm audio format is disabled |
| 10 | Settings changes persist after page reload | Edit interests, reload, verify interests unchanged |
| 11 | Source explorer shows trust scores and bias labels | Cross-check with `GET /sources` response |
| 12 | Pages load in <2s on 3G throttled connection | Lighthouse performance audit score >80 |
| 13 | Mobile layout is usable at 375px width | Manual test on iPhone SE viewport |
| 14 | Docker build succeeds and serves alongside API | `docker compose up` serves both frontend and API |

---

## Testing Strategy

- **Unit:** React Testing Library for component rendering and state
- **Integration:** Playwright E2E tests for critical flows (signup → dashboard → story detail → engagement)
- **Visual:** Chromatic or Percy for screenshot regression on perspective cards
- **API mocking:** MSW (Mock Service Worker) for isolated frontend tests
- **CI:** Add `npm test` and `npx playwright test` to GitHub Actions workflow

---

## Out of Scope (Handled by Other Priorities)

- Payment UI (Priority 2 — Stripe)
- Audio playback (Priority 3 — TTS)
- WebSocket live updates (Priority 4 — Async)
