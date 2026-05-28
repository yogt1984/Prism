# Resonance — Topic Media Impact Score

## Overview

Resonance is a composite metric that quantifies how much media attention and
impact a topic (story cluster) has accumulated. It answers: _"How significant is
this story in the current media landscape?"_

Unlike raw mention counts, Resonance weights contributions by **source
authority**, **audience engagement**, **source diversity**, and **recency** —
producing a single scalar that is both meaningful for ranking and decomposable
for transparency.

---

## Metric Definition

### Formula

```
Resonance(cluster, T) = breadth(cluster, T)
                      × Σ  [ trust(source_m) × engagement(m) × decay(age_m) ]
                        m∈T
```

Where:
- **m** is a single mention (article) within time window **T**
- **trust(source_m)** is the source's `trust_score` from the Source registry (0.0–1.0)
- **engagement(m)** = `1 + log₂(1 + reactions_m / platform_median)` — log-scaled
  engagement amplifier; defaults to 1.0 when reaction data is unavailable
- **breadth(cluster, T)** = `log₂(1 + n_distinct_sources)` — rewards coverage
  diversity; a story covered by 8 independent outlets scores higher than one
  outlet publishing 8 articles
- **decay(age_m)** = `e^(−λ × age_hours)` where `λ = ln(2) / half_life_hours`
  (default `half_life_hours = 24`, giving `λ ≈ 0.0289`)

### Derived Signals

| Signal | Definition | Purpose |
|--------|-----------|---------|
| **Momentum** | `Resonance(t) − Resonance(t − Δt)` (default Δt = 6h) | Rising vs fading stories |
| **Peak Resonance** | `max(Resonance)` over cluster lifetime | Historical high-water mark |
| **Persistence** | Hours where `Resonance > threshold` | Flash-in-the-pan vs sustained story |

### Design Rationale

- **Log-scaling engagement** prevents viral outliers from dominating the score.
- **Breadth as a multiplier** ensures single-source stories stay low regardless
  of engagement — aligning with Prism's multi-perspective principle.
- **Exponential decay** naturally ages out stale stories without manual cleanup.
- **Decomposability**: each component (trust, engagement, breadth, decay) is
  stored and queryable independently, so the score is never a black box.

### Parameter Defaults

| Parameter | Default | Configurable via |
|-----------|---------|------------------|
| `half_life_hours` | 24 | `settings.resonance_half_life_hours` |
| `window_hours` | 72 | `settings.resonance_window_hours` |
| `momentum_delta_hours` | 6 | `settings.resonance_momentum_delta_hours` |
| `platform_median_reactions` | 50 | `settings.resonance_platform_median` |

---

## Data Model

### New Model: `TopicResonance`

```python
class TopicResonance(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    cluster_id: int = Field(foreign_key="storycluster.id", index=True)
    resonance: float = 0.0            # composite score
    momentum: float = 0.0             # delta over momentum window
    peak_resonance: float = 0.0       # all-time max
    mention_count: int = 0            # raw article count in window
    source_count: int = 0             # distinct sources in window
    authority_weighted_sum: float = 0.0  # Σ trust(s) per mention
    breadth: float = 0.0              # log₂(1 + source_count)
    window_hours: int = 72
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

### StoryCluster Extension

Add a convenience field to `StoryCluster`:

```python
resonance_score: float = 0.0   # latest computed resonance (denormalized)
```

This enables sorting/filtering clusters by resonance without joining.

---

## Integration Points

- **A_AI**: computes resonance after analyzing a cluster (piggybacks on
  `analyze_cluster`)
- **P_AI**: uses `resonance_score` as a ranking signal alongside user interest
  vectors
- **API**: new `GET /stories?sort=resonance` query parameter; resonance fields
  included in story response
- **CLI**: `prism story list --sort resonance` flag
- **Metrics**: `resonance_computed_total` counter, `resonance_score` histogram

---

## Implementation Tasks

### T-RES.1: Add `TopicResonance` model and DB migration

**Files:** `src/prism/models.py`

**Work:**
- Add `TopicResonance` SQLModel class as specified above
- Add `resonance_score: float = 0.0` field to `StoryCluster`
- Ensure table is created via existing `SQLModel.metadata.create_all` path

**Acceptance Criteria:**
- [ ] `TopicResonance` table is created on engine init
- [ ] `StoryCluster` has `resonance_score` column with default 0.0
- [ ] Existing tests pass (no regressions on model imports)
- [ ] Unit test creates a `TopicResonance` row, persists it, and reads it back
      with all fields intact

---

### T-RES.2: Add resonance configuration parameters

**Files:** `src/prism/config.py`

**Work:**
- Add `resonance_half_life_hours: int = 24`
- Add `resonance_window_hours: int = 72`
- Add `resonance_momentum_delta_hours: int = 6`
- Add `resonance_platform_median: int = 50`

**Acceptance Criteria:**
- [ ] All four settings load with defaults when env vars are absent
- [ ] Each setting is overridable via `PRISM_RESONANCE_*` environment variables
- [ ] Unit test verifies default values and env-var override for at least one
      parameter

---

### T-RES.3: Implement core `compute_resonance` function

**Files:** new `src/prism/resonance.py`

**Work:**
- Pure function: `compute_resonance(articles, trust_map, engagements, now, config) -> ResonanceResult`
- `ResonanceResult` is a dataclass with: `resonance`, `mention_count`,
  `source_count`, `authority_weighted_sum`, `breadth`
- Implements the formula: breadth × Σ(trust × engagement × decay)
- No DB access — all inputs are passed in for testability

**Acceptance Criteria:**
- [ ] Single article from trust=1.0 source, no engagement, age=0 → resonance = `log₂(2) × 1.0 × 1.0 × 1.0 = 1.0`
- [ ] Two articles from same source → `source_count=1`, breadth = `log₂(2) = 1.0`
- [ ] Two articles from different sources → `source_count=2`, breadth = `log₂(3) ≈ 1.585`
- [ ] Article aged exactly `half_life_hours` → decay factor = 0.5
- [ ] Zero articles → resonance = 0.0, no division errors
- [ ] Engagement amplifier: 0 reactions → factor = 1.0; 50 reactions (= median) → factor = 2.0

---

### T-RES.4: Implement `compute_momentum` function

**Files:** `src/prism/resonance.py`

**Work:**
- `compute_momentum(current_resonance, previous_resonance) -> float`
- Simply `current - previous`; caller is responsible for providing the
  resonance at `t - delta`

**Acceptance Criteria:**
- [ ] Rising story: `compute_momentum(10.0, 3.0) == 7.0`
- [ ] Fading story: `compute_momentum(2.0, 8.0) == -6.0`
- [ ] Stable story: `compute_momentum(5.0, 5.0) == 0.0`

---

### T-RES.5: Wire resonance computation into A_AI

**Files:** `src/prism/agents/a_ai.py`

**Work:**
- After `analyze_cluster` commits perspectives, call `compute_resonance` with
  the cluster's articles and trust map (both already loaded in scope)
- Fetch the previous `TopicResonance` row (if any) to compute momentum
- Upsert `TopicResonance` row and update `StoryCluster.resonance_score`
- Add `resonance_computed_total` counter to `src/prism/metrics.py`

**Acceptance Criteria:**
- [ ] After `analyze_cluster`, a `TopicResonance` row exists for that cluster
- [ ] `StoryCluster.resonance_score` matches `TopicResonance.resonance`
- [ ] Re-running analysis on the same cluster updates (not duplicates) the
      resonance row
- [ ] `resonance_computed_total` counter increments on each computation
- [ ] Resonance computation failure does not block analysis (logged, not raised)

---

### T-RES.6: Expose resonance in API responses

**Files:** `src/prism/api/routes.py`

**Work:**
- Include `resonance_score` in story/cluster list and detail endpoints
- Add `sort=resonance` query parameter to `GET /stories` (default remains
  `first_seen` descending)
- Add `GET /stories/{id}/resonance` endpoint returning full `TopicResonance`
  breakdown

**Acceptance Criteria:**
- [ ] `GET /stories` response includes `resonance_score` field per story
- [ ] `GET /stories?sort=resonance` returns stories ordered by resonance desc
- [ ] `GET /stories/{id}/resonance` returns all decomposed fields (breadth,
      authority_weighted_sum, momentum, etc.)
- [ ] Stories with no resonance data yet return `resonance_score: 0.0`

---

### T-RES.7: Add resonance to CLI

**Files:** `src/prism/cli/story.py`

**Work:**
- Add `--sort resonance` option to `prism story list`
- Display resonance score and momentum in story list table
- Add `prism story resonance <cluster_id>` subcommand showing full breakdown

**Acceptance Criteria:**
- [ ] `prism story list --sort resonance` outputs stories sorted by resonance
- [ ] Resonance and momentum columns appear in the table output
- [ ] `prism story resonance <id>` prints all TopicResonance fields in readable
      format
- [ ] Commands work gracefully when no resonance data exists yet

---

### T-RES.8: Integrate resonance into P_AI ranking

**Files:** `src/prism/agents/p_ai.py`

**Work:**
- Add resonance as a weighted factor in story ranking alongside interest match
- Default weight: `0.3` (configurable via `settings.resonance_ranking_weight`)
- High-resonance stories get a ranking boost but don't override user interests

**Acceptance Criteria:**
- [ ] Between two stories with equal interest match, the higher-resonance story
      ranks first
- [ ] A low-interest, high-resonance story does not outrank a high-interest,
      low-resonance story (interest still dominates)
- [ ] `resonance_ranking_weight = 0.0` disables the boost entirely
- [ ] Unit test with mock stories verifies ranking order changes with resonance

---

## Task Dependency Graph

```
T-RES.1 (model)
   ├──► T-RES.2 (config)
   │       └──► T-RES.3 (core function)
   │               ├──► T-RES.4 (momentum)
   │               └──► T-RES.5 (A_AI wiring)
   │                       ├──► T-RES.6 (API)
   │                       ├──► T-RES.7 (CLI)
   │                       └──► T-RES.8 (P_AI ranking)
```

Tasks should be implemented in order T-RES.1 → T-RES.2 → T-RES.3 → T-RES.4 →
T-RES.5 → T-RES.6 → T-RES.7 → T-RES.8. Each task is independently testable
once its predecessors are complete.
