# 06_01 — Source Lifecycle Schema & Migration

**Parent:** 06 Source Auto-Discovery
**Must complete before:** 06_02 (candidate discovery writes new fields)

---

## Objective

Extend the `Source` model with lifecycle fields (`status`,
`discovered_via`, `probation_start`, validation counters, rejection
reason). Create Alembic migration. Backfill existing 30 seeded
sources with `status="seed"`. Add configuration settings for the
discovery pipeline thresholds.

---

## Current Source Model (`src/prism/models.py`, line 43–53)

```python
class Source(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    url: str = Field(unique=True)
    rss_url: str = ""
    trust_score: float = 0.5
    bias_label: BiasLabel = BiasLabel.UNKNOWN
    categories: str = ""
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
```

---

## New Enum

```python
class SourceStatus(StrEnum):
    SEED = "seed"             # hand-curated, never auto-demoted
    CANDIDATE = "candidate"   # discovered, not yet evaluated
    PROBATION = "probation"   # active but under validation
    TRUSTED = "trusted"       # passed validation, fully active
    REJECTED = "rejected"     # failed validation, inactive
```

---

## Updated Source Model

```python
class Source(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    url: str = Field(unique=True)
    rss_url: str = ""
    trust_score: float = 0.5
    bias_label: BiasLabel = BiasLabel.UNKNOWN
    categories: str = ""
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # ── Lifecycle (new) ──────────────────────────────────
    status: SourceStatus = SourceStatus.CANDIDATE
    discovered_via: str = ""          # "brave_search", "rss_reference", "manual"
    probation_start: datetime | None = None
    articles_validated: int = 0       # cross-referenced with trusted sources
    articles_failed: int = 0          # failed cross-validation
    sighting_count: int = 0           # times seen in Brave results
    last_evaluated: datetime | None = None
    rejection_reason: str = ""
```

**Field rationale:**
- `status`: lifecycle state machine (see 06 top-level spec)
- `discovered_via`: provenance for audit ("how did we find this source?")
- `sighting_count`: tracks how many discovery cycles have seen this domain;
  threshold of 3 triggers probation promotion (06_03)
- `articles_validated` / `articles_failed`: cross-validation scoreboard
  used by the evaluation job (06_04)
- `rejection_reason`: human-readable string for audit trail

---

## Alembic Migration

### File: `alembic/versions/007_add_source_lifecycle.py`

```python
"""Add source lifecycle fields.

Revision ID: 007
Revises: 006
"""
from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"

def upgrade() -> None:
    with op.batch_alter_table("source") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(), server_default="candidate", nullable=False))
        batch_op.add_column(sa.Column("discovered_via", sa.String(), server_default="", nullable=False))
        batch_op.add_column(sa.Column("probation_start", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("articles_validated", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("articles_failed", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("sighting_count", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("last_evaluated", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("rejection_reason", sa.String(), server_default="", nullable=False))

    # Backfill: existing seeded sources → status="seed"
    op.execute("UPDATE source SET status = 'seed' WHERE trust_score >= 0.5")

def downgrade() -> None:
    with op.batch_alter_table("source") as batch_op:
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("last_evaluated")
        batch_op.drop_column("sighting_count")
        batch_op.drop_column("articles_failed")
        batch_op.drop_column("articles_validated")
        batch_op.drop_column("probation_start")
        batch_op.drop_column("discovered_via")
        batch_op.drop_column("status")
```

**Note:** uses `batch_alter_table` because SQLite doesn't support
`ALTER TABLE ADD COLUMN` with defaults in all cases.

**Backfill logic:** all sources with `trust_score >= 0.5` are the
original 30 seeds (seed.py assigns 0.5–0.95). Sources created by
`_get_or_create_source` in D_AI get default `trust_score=0.5` but
those are the domain-extracted sources which should also be seeded.

---

## Configuration Additions

Add to `Settings` in `src/prism/config.py`:

```python
# Source auto-discovery
source_candidate_max_per_cycle: int = 5
source_probation_days: int = 14
source_promotion_min_articles: int = 10
source_promotion_min_ratio: float = 0.7
source_demotion_consecutive_failures: int = 5
source_rss_detect_timeout: float = 5.0
```

---

## Seed Script Update

Update `src/prism/seed.py` to set `status="seed"` on new inserts:

```python
source = Source(
    name=name,
    url=url,
    rss_url=rss_url,
    trust_score=trust,
    bias_label=bias,
    categories=categories,
    active=True,
    status=SourceStatus.SEED,       # new
    discovered_via="manual",         # new
)
```

Existing rows already backfilled by migration.

---

## Acceptance Criteria

| # | Criterion | Verification |
|---|-----------|--------------|
| 1 | Migration applies cleanly | `alembic upgrade head` succeeds |
| 2 | All 30 seeded sources have `status="seed"` | `SELECT count(*) FROM source WHERE status='seed'` → 30 |
| 3 | New Source defaults: `status="candidate"`, counters=0 | Insert source, verify defaults |
| 4 | `SourceStatus` enum has 5 values | `list(SourceStatus)` → 5 items |
| 5 | Downgrade removes all new columns | `alembic downgrade -1`, verify schema |
| 6 | Config settings have correct defaults | `settings.source_probation_days` → 14 |
| 7 | `seed_sources()` sets `status="seed"` on new inserts | Clear DB, run seed, verify |
| 8 | Existing model queries still work | `select(Source).where(Source.active == True)` unchanged |
| 9 | `Source.sighting_count` defaults to 0 | Create source, verify field |

---

## Testing Strategy

```python
def test_source_lifecycle_fields_exist():
    """New fields are accessible on Source model."""
    s = Source(name="Test", url="test.com")
    assert s.status == SourceStatus.CANDIDATE
    assert s.articles_validated == 0
    assert s.sighting_count == 0
    assert s.rejection_reason == ""

def test_migration_backfills_seed_status(engine):
    """After migration, seeded sources have status='seed'."""
    with Session(engine) as session:
        seeds = session.exec(
            select(Source).where(Source.status == "seed")
        ).all()
        assert len(seeds) == 30

def test_source_status_enum():
    """SourceStatus has expected values."""
    assert SourceStatus.SEED == "seed"
    assert SourceStatus.REJECTED == "rejected"
    assert len(SourceStatus) == 5

def test_config_defaults():
    """Discovery config settings have defaults."""
    from prism.config import Settings
    s = Settings(anthropic_api_key="test")
    assert s.source_candidate_max_per_cycle == 5
    assert s.source_probation_days == 14
```

---

## Files Changed

| File | Change |
|------|--------|
| `src/prism/models.py` | Add SourceStatus enum, 8 new fields on Source |
| `alembic/versions/007_add_source_lifecycle.py` | New migration |
| `src/prism/config.py` | Add 6 source discovery settings |
| `src/prism/seed.py` | Set `status="seed"` on new inserts |
| `tests/test_models.py` | Add lifecycle field tests |
