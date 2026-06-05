# 06 — Source Auto-Discovery

**Priority:** 6 (Scale — Long-term Value)
**Depends on:** None (D_AI extension)
**Unlocks:** Expanding coverage without manual curation, self-improving source registry

---

## Objective

Extend D_AI to autonomously discover, evaluate, and promote new news sources.
Currently the platform relies on 30 seeded sources plus manual CLI addition.
This task builds a pipeline that grows coverage organically while maintaining
quality standards.

---

## Current State

- `src/prism/seed.py`: 30 curated sources with hand-assigned trust scores and bias labels
- `prism source add`: manual CLI command to register a source
- `Source` model: `name`, `url`, `rss_url`, `trust_score`, `bias_label`, `active`, `categories`
- D_AI queries Brave Search API and fetches RSS feeds from active sources
- `min_source_trust_score` config (default 0.5) — sources below this are excluded from discovery

---

## Design: Source Lifecycle

```
                discover
UNKNOWN ──────────────────> CANDIDATE (trust=0.0, active=False)
                                 |
                                 | probation period (N articles cross-validated)
                                 v
                            PROBATION (trust=0.1, active=True, limited)
                                 |
                    ┌────────────┼────────────┐
                    |            |             |
                  promote     stagnate      demote
                    |            |             |
                    v            v             v
               TRUSTED      CANDIDATE     REJECTED
            (trust ≥ 0.5)   (reset)     (active=False)
```

### New Fields on `Source` Model

```
status (str): "seed", "candidate", "probation", "trusted", "rejected"
discovered_via (str | None): "brave_search" | "rss_reference" | "manual"
probation_start (datetime | None)
articles_validated (int, default 0)   — cross-referenced article count
articles_failed (int, default 0)      — articles that failed validation
last_evaluated (datetime | None)
rejection_reason (str | None)
```

Alembic migration: `009_add_source_lifecycle.py`

Existing 30 seeded sources get `status="seed"` (never auto-demoted).

---

## Implementation Tasks

### 1. Candidate Discovery (`src/prism/agents/discovery.py`)

During each Brave Search cycle, D_AI already retrieves results from many
domains. Extend the cycle to:

- **Extract unique domains** from Brave results that are not in the source registry
- **Filter out** known non-news domains (social media, forums, aggregators)
  - Blocklist: `reddit.com`, `twitter.com`, `facebook.com`, `youtube.com`, etc.
- **Create candidate Source** with:
  - `status="candidate"`, `trust_score=0.0`, `active=False`
  - `discovered_via="brave_search"`
  - `categories` inferred from the search query that found it
- **Deduplicate:** skip if domain already exists in Source table
- **Rate limit:** max 5 new candidates per discovery cycle (prevent flooding)

### 2. RSS Detection

For each new candidate, attempt to find an RSS feed:

- Check common paths: `/rss`, `/feed`, `/atom.xml`, `/rss.xml`, `/feed.xml`
- Parse `<link rel="alternate" type="application/rss+xml">` from homepage HTML
- If RSS found: store `rss_url` on the Source
- If no RSS: still keep candidate (Brave Search can still find articles)
- Timeout: 5s per URL, circuit breaker for repeated failures

### 3. Probation Pipeline

**Trigger:** when a candidate has been seen in >= 3 separate Brave Search results.

**Promotion to probation:**
- Set `status="probation"`, `trust_score=0.1`, `active=True`
- Set `probation_start=now()`
- Source now appears in discovery queries but with very low trust weight

**During probation (14-day window):**
- Articles from this source participate in normal clustering
- **Cross-validation:** for each article, check if the same event is covered by
  a trusted source (Jaccard similarity > 0.6 with a trusted cluster)
  - Match found: increment `articles_validated`
  - No match (and article makes unique claims): increment `articles_failed`
- Trust score grows linearly: `trust = 0.1 + (validated / (validated + failed)) * 0.4`
  - Max reachable during probation: 0.5

### 4. Promotion / Demotion

**Daily evaluation job** (add to APScheduler):

```python
def evaluate_probation_sources(session):
    for source in probation_sources_past_14_days(session):
        ratio = source.articles_validated / max(source.articles_validated + source.articles_failed, 1)
        if source.articles_validated >= 10 and ratio >= 0.7:
            promote(source)           # status="trusted", trust_score=0.5
        elif source.articles_validated < 3:
            reset_to_candidate(source) # not enough data, try again later
        else:
            reject(source)            # too many failures
```

**Promotion thresholds:**
- Minimum 10 validated articles during probation
- Validation ratio >= 70% (7 out of 10 articles corroborated)
- Result: `status="trusted"`, `trust_score=0.5`, continues earning trust organically

**Demotion triggers (for trusted sources):**
- If 5 consecutive articles fail cross-validation: demote to `probation`
- If trust score drops below 0.3 (via manual adjustment): demote to `candidate`

### 5. Bias Label Inference

For promoted sources, infer initial bias label from perspective analysis:

- Collect all `Perspective` records linked to this source
- Average sentiment across perspectives
- Map to bias label:
  - sentiment < -0.3: `left`
  - -0.3 to -0.1: `center_left`
  - -0.1 to 0.1: `center`
  - 0.1 to 0.3: `center_right`
  - sentiment > 0.3: `right`
- Store as initial bias label (can be manually overridden via CLI)

### 6. CLI Commands

```
prism source candidates          — list candidate sources
prism source probation           — list sources in probation with stats
prism source evaluate            — manually trigger evaluation cycle
prism source promote <id>        — manually promote a candidate
prism source reject <id> --reason "..." — manually reject with reason
prism source blocklist add <domain>     — add domain to discovery blocklist
prism source blocklist ls               — list blocked domains
```

### 7. API Endpoints

```
GET /sources/candidates?limit=20        — list candidates (admin)
GET /sources/probation                  — list probation sources with stats
POST /sources/{id}/promote              — manual promotion (admin)
POST /sources/{id}/reject               — manual rejection (admin)
```

### 8. Configuration

Add to `config.py`:

```
source_candidate_max_per_cycle (int, default 5)
source_probation_days (int, default 14)
source_promotion_min_articles (int, default 10)
source_promotion_min_ratio (float, default 0.7)
source_demotion_consecutive_failures (int, default 5)
```

---

## Domain Blocklist

Stored in `data/source_blocklist.txt` (one domain per line):

```
reddit.com
twitter.com
x.com
facebook.com
instagram.com
youtube.com
tiktok.com
linkedin.com
medium.com
substack.com
wikipedia.org
```

Loaded at startup, checked during candidate creation.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | New domains from Brave results create candidate sources | Run discovery cycle, verify new Source rows with `status=candidate` |
| 2 | Max 5 candidates per cycle | Run cycle with many new domains, verify cap enforced |
| 3 | Blocked domains are never added as candidates | Add `reddit.com` article to Brave results, verify no candidate |
| 4 | RSS detection finds feeds for common news sites | Test against known sites (BBC, NPR), verify `rss_url` populated |
| 5 | Candidate with 3+ sightings enters probation | Simulate 3 cycles with same domain, verify `status=probation` |
| 6 | Probation source articles participate in clustering | Verify articles from probation source appear in clusters |
| 7 | Cross-validation correctly counts validated articles | Create cluster with trusted + probation articles, verify count |
| 8 | Source with 10+ validated articles (70%+) is promoted | Run evaluation, verify `status=trusted`, `trust_score=0.5` |
| 9 | Source with <3 validated articles is reset | Run evaluation after 14 days, verify `status=candidate` |
| 10 | Source with <70% ratio is rejected | Run evaluation, verify `status=rejected`, `active=False` |
| 11 | Bias label is inferred from perspective sentiment | Promote source, verify `bias_label` matches avg sentiment |
| 12 | Seeded sources are never auto-demoted | Run demotion logic, verify `status=seed` sources unchanged |
| 13 | CLI `prism source candidates` lists candidates | Create candidates, run command, verify output |
| 14 | Daily evaluation job runs on schedule | Check APScheduler job list, verify `evaluate_probation_sources` |

---

## Testing Strategy

- **Unit:** test promotion/demotion logic with synthetic data
- **Unit:** test RSS detection with mocked HTTP responses
- **Unit:** test cross-validation scoring with known article pairs
- **Integration:** full lifecycle test: candidate → probation → trusted
- **Integration:** full lifecycle test: candidate → probation → rejected
- **Regression:** existing discovery tests unaffected (seeded sources unchanged)

---

## Metrics (New)

| Metric | Type | Description |
|--------|------|-------------|
| `source_candidates_discovered_total` | Counter | New candidates found |
| `source_promoted_total` | Counter | Sources promoted to trusted |
| `source_rejected_total` | Counter | Sources rejected after probation |
| `source_probation_active` | Gauge | Current probation count |
