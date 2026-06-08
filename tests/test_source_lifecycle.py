"""Tests for 06_01: Source lifecycle schema, migration, config, and seed."""

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine as sa_create_engine, inspect as sa_inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from prism.models import Source, SourceStatus


# ── Helpers ─────────────────────────────────────────────────────────


def _alembic_cfg(url: str) -> Config:
    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", url)
    return cfg


# ── SourceStatus enum ───────────────────────────────────────────────


def test_source_status_enum_values():
    assert SourceStatus.SEED == "seed"
    assert SourceStatus.CANDIDATE == "candidate"
    assert SourceStatus.PROBATION == "probation"
    assert SourceStatus.TRUSTED == "trusted"
    assert SourceStatus.REJECTED == "rejected"


def test_source_status_has_5_values():
    assert len(SourceStatus) == 5


# ── Source model defaults ───────────────────────────────────────────


def test_source_lifecycle_defaults():
    """New Source has correct lifecycle defaults."""
    s = Source(name="Test", url="test.com")
    assert s.status == SourceStatus.CANDIDATE
    assert s.discovered_via == ""
    assert s.probation_start is None
    assert s.articles_validated == 0
    assert s.articles_failed == 0
    assert s.sighting_count == 0
    assert s.last_evaluated is None
    assert s.rejection_reason == ""


def test_source_lifecycle_fields_settable():
    """Lifecycle fields can be set on construction."""
    s = Source(
        name="New",
        url="new.com",
        status=SourceStatus.PROBATION,
        discovered_via="brave_search",
        sighting_count=3,
        articles_validated=5,
        articles_failed=1,
        rejection_reason="",
    )
    assert s.status == SourceStatus.PROBATION
    assert s.discovered_via == "brave_search"
    assert s.sighting_count == 3
    assert s.articles_validated == 5


def test_source_existing_fields_preserved():
    """Existing fields still work alongside new lifecycle fields."""
    s = Source(
        name="Reuters",
        url="reuters.com",
        trust_score=0.95,
        active=True,
        status=SourceStatus.SEED,
    )
    assert s.name == "Reuters"
    assert s.trust_score == 0.95
    assert s.active is True
    assert s.status == SourceStatus.SEED


# ── DB roundtrip ────────────────────────────────────────────────────


def test_source_lifecycle_persists(tmp_path):
    """Lifecycle fields survive a DB roundtrip."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        s = Source(
            name="New Site",
            url="newsite.com",
            status=SourceStatus.PROBATION,
            discovered_via="brave_search",
            sighting_count=3,
            articles_validated=7,
            articles_failed=2,
        )
        session.add(s)
        session.commit()
        sid = s.id

    with Session(engine) as session:
        loaded = session.get(Source, sid)
        assert loaded.status == SourceStatus.PROBATION
        assert loaded.discovered_via == "brave_search"
        assert loaded.sighting_count == 3
        assert loaded.articles_validated == 7
        assert loaded.articles_failed == 2


def test_source_query_by_status(tmp_path):
    """Can query sources by status."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(name="Seed", url="seed.com", status=SourceStatus.SEED))
        session.add(Source(name="Cand", url="cand.com", status=SourceStatus.CANDIDATE))
        session.add(Source(name="Prob", url="prob.com", status=SourceStatus.PROBATION))
        session.commit()

    with Session(engine) as session:
        seeds = session.exec(select(Source).where(Source.status == SourceStatus.SEED)).all()
        assert len(seeds) == 1
        assert seeds[0].name == "Seed"

        active = session.exec(select(Source).where(Source.active == True)).all()  # noqa: E712
        assert len(active) == 3


def test_existing_queries_still_work(tmp_path):
    """Existing query patterns (active filter) work with new fields."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(name="A", url="a.com", active=True))
        session.add(Source(name="B", url="b.com", active=False))
        session.commit()

    with Session(engine) as session:
        active = session.exec(select(Source).where(Source.active == True)).all()  # noqa: E712
        assert len(active) == 1
        assert active[0].name == "A"


# ── Config settings ─────────────────────────────────────────────────


def test_config_discovery_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None
    s = cfg.Settings()  # type: ignore[call-arg]
    assert s.source_candidate_max_per_cycle == 5
    assert s.source_probation_days == 14
    assert s.source_promotion_min_articles == 10
    assert s.source_promotion_min_ratio == 0.7
    assert s.source_demotion_consecutive_failures == 5
    assert s.source_rss_detect_timeout == 5.0
    cfg._settings = None


def test_config_discovery_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("SOURCE_PROBATION_DAYS", "7")
    monkeypatch.setenv("SOURCE_PROMOTION_MIN_ARTICLES", "20")
    import prism.config as cfg
    cfg._settings = None
    s = cfg.Settings()  # type: ignore[call-arg]
    assert s.source_probation_days == 7
    assert s.source_promotion_min_articles == 20
    cfg._settings = None


# ── Seed script ─────────────────────────────────────────────────────


def test_seed_sets_status_seed(tmp_path):
    """seed_sources() sets status='seed' on new inserts."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    from prism.seed import seed_sources
    count = seed_sources(engine)
    assert count == 30

    with Session(engine) as session:
        seeds = session.exec(select(Source).where(Source.status == SourceStatus.SEED)).all()
        assert len(seeds) == 30
        for s in seeds:
            assert s.discovered_via == "manual"


# ── Alembic migration 009 ──────────────────────────────────────────


def test_alembic_head_is_009(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")

    engine = sa_create_engine(url)
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert rev == "009"


def test_migration_009_adds_lifecycle_columns(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")

    engine = sa_create_engine(url)
    cols = {c["name"] for c in sa_inspect(engine).get_columns("source")}
    expected_new = {
        "status", "discovered_via", "probation_start",
        "articles_validated", "articles_failed", "sighting_count",
        "last_evaluated", "rejection_reason",
    }
    assert expected_new.issubset(cols)


def test_migration_009_backfills_seed_status(tmp_path):
    """Migration backfills existing sources with trust_score >= 0.5 as seed."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    cfg = _alembic_cfg(url)

    # Upgrade to 008 first, insert some sources
    command.upgrade(cfg, "008")
    engine = sa_create_engine(url)
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO source (name, url, trust_score, created_at) "
            "VALUES ('High Trust', 'high.com', 0.9, '2026-01-01')"
        ))
        conn.execute(text(
            "INSERT INTO source (name, url, trust_score, created_at) "
            "VALUES ('Low Trust', 'low.com', 0.3, '2026-01-01')"
        ))
        conn.commit()

    # Now upgrade to 009 — triggers backfill
    command.upgrade(cfg, "009")
    with engine.connect() as conn:
        high = conn.execute(text("SELECT status FROM source WHERE url='high.com'")).scalar()
        low = conn.execute(text("SELECT status FROM source WHERE url='low.com'")).scalar()
    assert high == "seed"
    assert low == "candidate"  # trust_score < 0.5, not backfilled


def test_migration_009_downgrade(tmp_path):
    """Downgrade from 009 removes lifecycle columns."""
    url = f"sqlite:///{tmp_path / 'test.db'}"
    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "008")

    engine = sa_create_engine(url)
    cols = {c["name"] for c in sa_inspect(engine).get_columns("source")}
    assert "status" not in cols
    assert "sighting_count" not in cols
    assert "rejection_reason" not in cols
    # Original columns still there
    assert "name" in cols
    assert "url" in cols
    assert "trust_score" in cols
