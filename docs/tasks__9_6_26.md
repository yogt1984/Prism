# Next Tasks — 2026-06-09

Status snapshot: backend MVP complete (882 tests), web frontend substantially
complete (1058 tests, 12 routes), Stripe checkout wired end-to-end, source
auto-discovery operational, engagement tracking live.

---

## Priority 1: Close the Personalization Loop

The frontend now sends engagement signals (open/read/save/skip). P_AI doesn't
use them yet — story ranking is still static interest matching.

### T1.1: Engagement weight calculation in P_AI

**Files:** `src/prism/agents/p_ai.py`

- Add `_compute_engagement_weights(user_id, engine) -> dict[str, float]`
- Query last 30 days of engagements: `save` = +2.0, `read` (>30s) = +1.0,
  `open` = +0.5, `skip` = -1.0
- Normalize per-category to 0.0–1.0 range
- 4 tests: saves boost, skips reduce, empty history safe, mixed actions

### T1.2: Integrate engagement weights into story scoring

**Files:** `src/prism/agents/p_ai.py`

- Modify `score_story()` to accept `engagement_weights`
- Add engagement bonus: `sum(weights.get(cat, 0) * 3.0 for cat in story_cats)`
- Backward compatible — no engagement data = identical behavior
- 4 tests: weight boost, doesn't override interest, no-data fallback, sort order

---

## Priority 2: Story Perspective Toggles

The core product differentiator. `PerspectiveViewer` exists but needs a
comparison mode showing different source framings side-by-side.

### T2.1: Side-by-side perspective comparison

**Files:** `frontend/components/story/PerspectiveViewer.tsx` (edit),
possibly new `PerspectiveCompare.tsx`

- Add toggle: "All perspectives" (current list view) vs "Compare" (2-up
  side-by-side with source name, bias badge, sentiment indicator)
- Highlight framing differences (key claims that appear in one perspective
  but not others)
- Responsive: stacked on mobile, side-by-side on md+
- Tests: toggle renders, compare mode shows 2 perspectives, bias badges visible

---

## Priority 3: Security Hardening

Pre-production essentials. No dependencies.

### T3.1: Hash API keys at rest

**Files:** `src/prism/models.py`, `src/prism/api/routes.py`,
`src/prism/onboarding.py`

- Store `api_key_hash` (SHA-256), clear plaintext after first reveal
- Update `require_api_key()` to compare against hash
- 4 tests: auth succeeds, auth fails, hash != raw, raw shown once

### T3.2: API rate limiting

**Files:** `src/prism/api/app.py`, new `src/prism/api/rate_limit.py`

- In-memory sliding-window: 60 req/min public, 120 req/min authenticated
- Return 429 with `Retry-After` header
- 4 tests: under limit OK, over limit 429, independent IPs, window slides

### T3.3: User-scoped access control

**Files:** `src/prism/api/routes.py`

- Enforce `auth_user.id == user_id` on all authenticated endpoints
- Return 403 for cross-user access attempts
- 4 tests: cannot read others, cannot list others' briefings, own access OK,
  clear 403 message

---

## Priority 4: Deduplication Improvement

Improves story cluster quality. D_AI currently uses Jaccard only.

### T4.1: TF-IDF similarity as Jaccard fallback

**Files:** `src/prism/agents/d_ai.py`

- Add `_tfidf_similarity(a, b) -> float` using sklearn (optional dep)
- Tiebreaker when Jaccard is 0.4–threshold: check TF-IDF at 0.5
- Graceful fallback if sklearn unavailable
- 4 tests: catches rewording, separates different events, no-sklearn fallback,
  200 articles < 2s

### T4.2: Named entity overlap

**Files:** `src/prism/agents/d_ai.py`

- Extract capitalized multi-word sequences via regex
- Combined score: `0.5*jaccard + 0.3*tfidf + 0.2*entity`
- 4 tests: same-person clusters, different-entity separates, short titles safe,
  score bounded

---

## Priority 5: Frontend Polish

### T5.1: Dashboard onboarding empty states

**Files:** `frontend/components/dashboard/` (multiple)

- Empty states for: no stories yet, no briefings, no keywords tracked
- Contextual CTAs: "Add your first keyword", "Generate your first briefing"
- Tests for each empty state component

### T5.2: Pro badge in Sidebar and Dashboard header

**Files:** `frontend/components/dashboard/Sidebar.tsx`

- Show PlanBadge next to user greeting for Pro users
- Hide "Upgrade to Pro" link for Pro users (already done)
- Test: badge visible for pro, hidden for free

---

## Priority 6: Database Migrations

Foundation for future schema changes.

### T6.1: Alembic infrastructure

**Files:** new `alembic.ini`, `alembic/env.py`,
`alembic/versions/001_initial.py`

- Generate initial migration from SQLModel metadata
- Add `prism db upgrade` CLI command
- 4 tests: fresh DB, existing DB detection, downgrade, CLI

### T6.2: DateTime indexes

**Files:** new `alembic/versions/002_add_datetime_indexes.py`

- Index: `StoryCluster.first_seen`, `Article.fetched_at`,
  `Briefing.created_at`, `Engagement.created_at`
- 4 tests: applies cleanly, downgrade removes, EXPLAIN uses index, no data loss

---

## Deprioritized

These items exist in the roadmap but are deferred:

- **Async FastAPI / WebSocket** (Phase 04) — premature without concurrent users
- **Prometheus metrics export** (Phase 05) — in-process metrics sufficient for now
- **TTS audio synthesis** (Phase 03) — text-first product direction
- **JSON feed formatter** (M16.1) — API access exists, structured format is low demand
- **Prompt versioning** (M17) — requires Alembic (T6.1) first

---

## Dependency Graph

```
T1.1 → T1.2 (engagement weights → scoring integration)
T3.1, T3.2, T3.3 (independent, no deps)
T4.1 → T4.2 (TF-IDF → entity overlap)
T6.1 → T6.2 (Alembic → indexes)
T2.1 (independent)
T5.1, T5.2 (independent)
```

**Recommended order:** T1.1 → T1.2 → T2.1 → T3.1 → T3.2 → T3.3 → T4.1 →
T4.2 → T5.1 → T5.2 → T6.1 → T6.2
