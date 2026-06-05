# 06_04 — Cross-Validation, Promotion & Demotion

**Parent:** 06 Source Auto-Discovery
**Depends on:** 06_03 (sources in probation, articles flowing)

---

## Objective

Implement the trust-building pipeline for probation sources:

1. **Cross-validation** — for each article from a probation source,
   check if a trusted source covers the same event. Score the source.
2. **Daily evaluation** — after the 14-day probation window, promote
   or reject sources based on validation ratio.
3. **Bias label inference** — for promoted sources, compute initial
   bias label from perspective sentiment data.
4. **Demotion** — demote trusted sources that start failing validation.

---

## Part 1: Cross-Validation

### Logic: `src/prism/agents/source_lifecycle.py`

After A_AI analyzes a cluster, check whether probation-source articles
are corroborated by trusted sources in the same cluster.

```python
from prism.models import Article, Source, SourceStatus, StoryCluster

def cross_validate_cluster(cluster_id: int, engine: Engine) -> None:
    """Score probation source articles in a cluster against trusted sources.

    For each article from a probation source in this cluster:
    - If the cluster also contains an article from a trusted/seed source
      → increment articles_validated
    - If the cluster contains ONLY probation articles (no trusted corroboration)
      AND the cluster has unique claims not seen elsewhere
      → increment articles_failed
    """
    with Session(engine) as session:
        articles = session.exec(
            select(Article, Source).join(Source, Article.source_id == Source.id).where(
                Article.cluster_id == cluster_id
            )
        ).all()

        if not articles:
            return

        trusted_present = any(
            source.status in (SourceStatus.SEED, SourceStatus.TRUSTED)
            for _, source in articles
        )

        probation_sources: dict[int, Source] = {}
        for article, source in articles:
            if source.status == SourceStatus.PROBATION:
                probation_sources[source.id] = source

        if not probation_sources:
            return  # no probation sources in this cluster

        for source_id, source in probation_sources.items():
            if trusted_present:
                source.articles_validated += 1
                logger.debug(
                    "Source '%s' validated (cluster %d has trusted sources)",
                    source.name, cluster_id,
                )
            else:
                # Only count as failure if cluster has few articles
                # (single-source clusters are suspicious)
                cluster = session.get(StoryCluster, cluster_id)
                if cluster and cluster.article_count <= 2:
                    source.articles_failed += 1
                    logger.debug(
                        "Source '%s' failed validation (cluster %d, no trusted corroboration)",
                        source.name, cluster_id,
                    )
                # else: multi-source cluster without trusted sources is ambiguous, skip

        session.commit()
```

### Integration Point

Call `cross_validate_cluster()` at the end of A_AI's analysis of each
cluster (in `src/prism/agents/a_ai.py`), after setting
`cluster.status = ANALYZED`:

```python
from prism.agents.source_lifecycle import cross_validate_cluster

# After analysis completes:
cross_validate_cluster(cluster.id, engine)
```

---

## Part 2: Daily Evaluation Job

### Logic: `src/prism/agents/source_lifecycle.py`

```python
from datetime import timedelta

def evaluate_probation_sources(engine: Engine) -> dict[str, int]:
    """Evaluate all probation sources past their probation window.

    Returns {"promoted": N, "rejected": N, "reset": N}.
    """
    now = datetime.now(UTC)
    probation_days = settings.source_probation_days
    min_articles = settings.source_promotion_min_articles
    min_ratio = settings.source_promotion_min_ratio
    results = {"promoted": 0, "rejected": 0, "reset": 0}

    with Session(engine) as session:
        sources = session.exec(
            select(Source).where(
                Source.status == SourceStatus.PROBATION,
                Source.probation_start != None,
                Source.probation_start <= now - timedelta(days=probation_days),
            )
        ).all()

        for source in sources:
            total = source.articles_validated + source.articles_failed
            ratio = source.articles_validated / max(total, 1)

            source.last_evaluated = now

            if source.articles_validated >= min_articles and ratio >= min_ratio:
                # Promote
                source.status = SourceStatus.TRUSTED
                source.trust_score = 0.5
                _infer_bias_label(source, session)
                results["promoted"] += 1
                logger.info(
                    "Source '%s' promoted to trusted (validated=%d, ratio=%.2f)",
                    source.name, source.articles_validated, ratio,
                )
            elif source.articles_validated < 3:
                # Not enough data — reset to candidate for another round
                source.status = SourceStatus.CANDIDATE
                source.active = False
                source.trust_score = 0.0
                source.probation_start = None
                source.articles_validated = 0
                source.articles_failed = 0
                results["reset"] += 1
                logger.info(
                    "Source '%s' reset to candidate (insufficient data: %d validated)",
                    source.name, source.articles_validated,
                )
            else:
                # Too many failures — reject
                source.status = SourceStatus.REJECTED
                source.active = False
                source.trust_score = 0.0
                source.rejection_reason = (
                    f"Validation ratio {ratio:.2f} < {min_ratio} "
                    f"({source.articles_validated}/{total})"
                )
                results["rejected"] += 1
                logger.info(
                    "Source '%s' rejected (ratio=%.2f, reason: %s)",
                    source.name, ratio, source.rejection_reason,
                )

        session.commit()

    return results
```

### APScheduler Job

Add to `build_scheduler()` in `src/prism/main.py`:

```python
from prism.agents.source_lifecycle import evaluate_probation_sources

scheduler.add_job(
    lambda: evaluate_probation_sources(get_engine()),
    "cron",
    hour=0,    # midnight daily
    minute=30,
    id="source_evaluation",
)
```

---

## Part 3: Bias Label Inference

```python
from prism.models import Perspective

def _infer_bias_label(source: Source, session: Session) -> None:
    """Infer initial bias label from perspective sentiment data.

    Collects all Perspective records linked to articles from this source.
    Maps average sentiment to a bias label:
      < -0.3 → left
      -0.3 to -0.1 → center_left
      -0.1 to 0.1 → center
      0.1 to 0.3 → center_right
      > 0.3 → right
    """
    from prism.models import Article, BiasLabel

    perspectives = session.exec(
        select(Perspective).join(
            Article, Perspective.cluster_id == Article.cluster_id
        ).where(Article.source_id == source.id)
    ).all()

    if not perspectives:
        source.bias_label = BiasLabel.UNKNOWN
        return

    avg_sentiment = sum(p.sentiment for p in perspectives) / len(perspectives)

    if avg_sentiment < -0.3:
        source.bias_label = BiasLabel.LEFT
    elif avg_sentiment < -0.1:
        source.bias_label = BiasLabel.CENTER_LEFT
    elif avg_sentiment <= 0.1:
        source.bias_label = BiasLabel.CENTER
    elif avg_sentiment <= 0.3:
        source.bias_label = BiasLabel.CENTER_RIGHT
    else:
        source.bias_label = BiasLabel.RIGHT

    logger.info(
        "Source '%s' bias inferred: %s (avg_sentiment=%.3f, n=%d)",
        source.name, source.bias_label.value, avg_sentiment, len(perspectives),
    )
```

---

## Part 4: Demotion of Trusted Sources

```python
def check_trusted_demotion(engine: Engine) -> int:
    """Demote trusted sources with consecutive validation failures.

    Criteria: articles_failed >= source_demotion_consecutive_failures
    while articles_validated has not increased since last evaluation.
    """
    threshold = settings.source_demotion_consecutive_failures
    demoted = 0

    with Session(engine) as session:
        sources = session.exec(
            select(Source).where(
                Source.status == SourceStatus.TRUSTED,
                Source.articles_failed >= threshold,
            )
        ).all()

        for source in sources:
            source.status = SourceStatus.PROBATION
            source.trust_score = 0.1
            source.probation_start = datetime.now(UTC)
            source.articles_validated = 0
            source.articles_failed = 0
            demoted += 1
            logger.warning(
                "Source '%s' demoted to probation (%d consecutive failures)",
                source.name, threshold,
            )

        session.commit()

    return demoted
```

Called within `evaluate_probation_sources()` or as a separate daily check.

**Seed sources are never demoted:**
```python
# All queries filter on Source.status == SourceStatus.TRUSTED
# Seeds have status == SourceStatus.SEED → excluded automatically
```

---

## Trust Score During Probation

While in probation, trust score updates linearly:
```python
trust = 0.1 + (validated / max(validated + failed, 1)) * 0.4
```
Max reachable: 0.5 (at 100% validation ratio).

This is recalculated in `cross_validate_cluster()`:
```python
total = source.articles_validated + source.articles_failed
source.trust_score = 0.1 + (source.articles_validated / max(total, 1)) * 0.4
```

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Cluster with probation + trusted articles → validated++ | Create mixed cluster, verify count |
| 2 | Single-source probation cluster → failed++ | Create lone cluster, verify count |
| 3 | Source with 10+ validated, 70%+ ratio promoted | Set counts, run evaluation, verify |
| 4 | Source with <3 validated reset to candidate | Set count=2, evaluate, verify |
| 5 | Source with <70% ratio rejected | Set 5/10, evaluate, verify `rejection_reason` |
| 6 | Bias label inferred on promotion | Promote source with perspectives, verify label |
| 7 | No perspectives → `UNKNOWN` bias label | Promote source without perspectives, verify |
| 8 | Trusted source with 5 failures demoted | Set failures=5, run check, verify probation |
| 9 | Seed sources never demoted | Set seed failures=10, verify status unchanged |
| 10 | Evaluation job runs daily at 00:30 | Check scheduler job list |
| 11 | Trust score formula correct during probation | 8/10 validated → trust=0.42 |
| 12 | `last_evaluated` timestamp set | Run evaluation, verify field |

---

## Testing Strategy

```python
def test_cross_validate_with_trusted(engine, populated_db):
    """Probation source validated when cluster has trusted source."""
    # Setup: cluster with 1 trusted article + 1 probation article
    # Run cross_validate_cluster
    # Verify probation source.articles_validated incremented

def test_cross_validate_lone_cluster(engine):
    """Probation source penalized in single-source cluster."""
    # Setup: cluster with only 1 probation article, article_count=1
    # Run cross_validate_cluster
    # Verify probation source.articles_failed incremented

def test_promote_source(engine):
    """Source with 12 validated / 3 failed = 80% is promoted."""
    # Setup: probation source, articles_validated=12, articles_failed=3
    # probation_start = 15 days ago
    results = evaluate_probation_sources(engine)
    assert results["promoted"] == 1
    # Verify status=TRUSTED, trust_score=0.5

def test_reject_source(engine):
    """Source with 5 validated / 8 failed = 38% is rejected."""
    results = evaluate_probation_sources(engine)
    assert results["rejected"] == 1
    # Verify rejection_reason contains ratio

def test_reset_insufficient_data(engine):
    """Source with 2 validated articles reset to candidate."""
    results = evaluate_probation_sources(engine)
    assert results["reset"] == 1

def test_seed_never_demoted(engine, populated_db):
    """Seed sources immune to demotion."""
    with Session(engine) as session:
        seed = session.exec(select(Source).where(Source.status == "seed")).first()
        seed.articles_failed = 100
        session.commit()
    demoted = check_trusted_demotion(engine)
    assert demoted == 0  # seeds excluded from query

def test_bias_inference():
    """Sentiment → bias label mapping."""
    # avg=-0.4 → LEFT, avg=0.0 → CENTER, avg=0.35 → RIGHT
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/agents/source_lifecycle.py` | Add cross_validate, evaluate, infer bias, demote |
| `src/prism/agents/a_ai.py` | Call cross_validate_cluster after analysis |
| `src/prism/main.py` | Add source_evaluation cron job |
| `tests/test_source_lifecycle.py` | Cross-validation, promotion, demotion tests |
