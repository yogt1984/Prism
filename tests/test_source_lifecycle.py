"""Tests for 06_01 / 06_03 / 06_04: Source lifecycle schema, migration, and pipeline."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine as sa_create_engine, inspect as sa_inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from prism.agents.source_lifecycle import (
    check_trusted_demotion,
    cross_validate_cluster,
    evaluate_probation_sources,
    promote_to_probation,
)
from prism.models import (
    Article,
    BiasLabel,
    Perspective,
    Source,
    SourceStatus,
    StoryCluster,
    StoryStatus,
)


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


# ── Probation promotion (06_03) ────────────────────────────────────


def test_promote_to_probation(tmp_path):
    """Candidate with 3 sightings is promoted."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(
            name="Test", url="test.com",
            status=SourceStatus.CANDIDATE, sighting_count=3,
        ))
        session.commit()

    count = promote_to_probation(engine)
    assert count == 1

    with Session(engine) as session:
        src = session.exec(select(Source).where(Source.url == "test.com")).first()
        assert src.status == SourceStatus.PROBATION
        assert src.active is True
        assert src.trust_score == pytest.approx(0.1)
        assert src.probation_start is not None


def test_promote_skips_low_sighting(tmp_path):
    """Candidate with <3 sightings not promoted."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(
            name="Low", url="low.com",
            status=SourceStatus.CANDIDATE, sighting_count=2,
        ))
        session.commit()

    count = promote_to_probation(engine)
    assert count == 0

    with Session(engine) as session:
        src = session.exec(select(Source).where(Source.url == "low.com")).first()
        assert src.status == SourceStatus.CANDIDATE


def test_promote_skips_non_candidate(tmp_path):
    """Already-probation or seed sources not re-promoted."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(
            name="Seed", url="seed.com",
            status=SourceStatus.SEED, sighting_count=10,
        ))
        session.add(Source(
            name="Prob", url="prob.com",
            status=SourceStatus.PROBATION, sighting_count=5,
        ))
        session.commit()

    count = promote_to_probation(engine)
    assert count == 0


def test_promote_multiple_candidates(tmp_path):
    """Multiple candidates promoted in one call."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        for i in range(3):
            session.add(Source(
                name=f"Site{i}", url=f"site{i}.com",
                status=SourceStatus.CANDIDATE, sighting_count=3 + i,
            ))
        session.commit()

    count = promote_to_probation(engine)
    assert count == 3

    with Session(engine) as session:
        all_prob = session.exec(
            select(Source).where(Source.status == SourceStatus.PROBATION)
        ).all()
        assert len(all_prob) == 3


def test_promote_idempotent(tmp_path):
    """Running promote twice doesn't re-promote or error."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(
            name="Test", url="test.com",
            status=SourceStatus.CANDIDATE, sighting_count=3,
        ))
        session.commit()

    assert promote_to_probation(engine) == 1
    assert promote_to_probation(engine) == 0  # already probation


# ── Cross-validation (06_04) ───────────────────────────────────────


def _make_cluster_with_articles(engine, sources_and_statuses, article_count=None):
    """Helper: create a cluster with articles from given sources.

    sources_and_statuses: list of (name, url, status) tuples.
    Returns (cluster_id, source_ids).
    """
    with Session(engine) as session:
        cluster = StoryCluster(
            headline="Test cluster",
            article_count=article_count or len(sources_and_statuses),
            status=StoryStatus.ANALYZED,
        )
        session.add(cluster)
        session.commit()
        session.refresh(cluster)
        cid = cluster.id

        source_ids = []
        for name, url, status in sources_and_statuses:
            src = Source(name=name, url=url, status=status, active=True)
            session.add(src)
            session.commit()
            session.refresh(src)
            source_ids.append(src.id)

            article = Article(
                cluster_id=cid,
                source_id=src.id,
                title=f"Article from {name}",
                url=f"https://{url}/article",
            )
            session.add(article)

        session.commit()
    return cid, source_ids


def test_cross_validate_with_trusted(tmp_path):
    """Probation source validated when cluster has trusted source."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    cid, sids = _make_cluster_with_articles(engine, [
        ("Trusted", "trusted.com", SourceStatus.SEED),
        ("Prob", "prob.com", SourceStatus.PROBATION),
    ])

    cross_validate_cluster(cid, engine)

    with Session(engine) as session:
        src = session.get(Source, sids[1])
        assert src.articles_validated == 1
        assert src.articles_failed == 0


def test_cross_validate_lone_cluster(tmp_path):
    """Probation source penalized in single-source cluster."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    cid, sids = _make_cluster_with_articles(engine, [
        ("Prob", "prob.com", SourceStatus.PROBATION),
    ], article_count=1)

    cross_validate_cluster(cid, engine)

    with Session(engine) as session:
        src = session.get(Source, sids[0])
        assert src.articles_failed == 1
        assert src.articles_validated == 0


def test_cross_validate_multi_source_no_trusted_ambiguous(tmp_path):
    """Multi-source cluster without trusted sources → no failure (ambiguous)."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    cid, sids = _make_cluster_with_articles(engine, [
        ("Prob1", "prob1.com", SourceStatus.PROBATION),
        ("Prob2", "prob2.com", SourceStatus.PROBATION),
        ("Prob3", "prob3.com", SourceStatus.PROBATION),
    ], article_count=3)

    cross_validate_cluster(cid, engine)

    with Session(engine) as session:
        for sid in sids:
            src = session.get(Source, sid)
            assert src.articles_failed == 0
            assert src.articles_validated == 0


def test_cross_validate_trust_score_updates(tmp_path):
    """Trust score formula: 0.1 + (validated / total) * 0.4."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    # Pre-set: 8 validated, 2 failed → after one more validated: 9/12
    with Session(engine) as session:
        src = Source(
            name="Prob", url="prob.com", status=SourceStatus.PROBATION,
            articles_validated=8, articles_failed=2,
        )
        session.add(src)
        session.commit()
        sid = src.id

        trusted = Source(name="AP", url="ap.com", status=SourceStatus.SEED)
        session.add(trusted)
        session.commit()

        cluster = StoryCluster(headline="Test", article_count=2, status=StoryStatus.ANALYZED)
        session.add(cluster)
        session.commit()
        session.refresh(cluster)
        cid = cluster.id

        session.add(Article(cluster_id=cid, source_id=sid, title="A", url="https://prob.com/a"))
        session.add(Article(cluster_id=cid, source_id=trusted.id, title="B", url="https://ap.com/a"))
        session.commit()

    cross_validate_cluster(cid, engine)

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.articles_validated == 9
        # trust = 0.1 + (9/11) * 0.4 ≈ 0.427
        expected = 0.1 + (9 / 11) * 0.4
        assert abs(src.trust_score - expected) < 0.01


def test_cross_validate_no_probation_noop(tmp_path):
    """Cluster with no probation sources → no changes."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    cid, _ = _make_cluster_with_articles(engine, [
        ("Trusted", "trusted.com", SourceStatus.SEED),
        ("Also Trusted", "also.com", SourceStatus.TRUSTED),
    ])

    cross_validate_cluster(cid, engine)  # should not crash


# ── Evaluation (06_04) ─────────────────────────────────────────────


def _make_probation_source(engine, url, validated, failed, days_ago=15):
    """Helper: create a probation source with given stats."""
    with Session(engine) as session:
        src = Source(
            name=url, url=url,
            status=SourceStatus.PROBATION,
            active=True,
            trust_score=0.1,
            probation_start=datetime.now(UTC) - timedelta(days=days_ago),
            articles_validated=validated,
            articles_failed=failed,
        )
        session.add(src)
        session.commit()
        return src.id


def test_evaluate_promotes_good_source(tmp_path):
    """Source with 12 validated / 3 failed = 80% is promoted."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    sid = _make_probation_source(engine, "good.com", validated=12, failed=3)

    results = evaluate_probation_sources(engine)
    assert results["promoted"] == 1

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.status == SourceStatus.TRUSTED
        assert src.trust_score == pytest.approx(0.5)
        assert src.last_evaluated is not None


def test_evaluate_rejects_bad_source(tmp_path):
    """Source with 5 validated / 8 failed = 38% is rejected."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    sid = _make_probation_source(engine, "bad.com", validated=5, failed=8)

    results = evaluate_probation_sources(engine)
    assert results["rejected"] == 1

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.status == SourceStatus.REJECTED
        assert src.active is False
        assert src.trust_score == 0.0
        assert "ratio" in src.rejection_reason.lower()


def test_evaluate_resets_insufficient_data(tmp_path):
    """Source with 2 validated articles reset to candidate."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    sid = _make_probation_source(engine, "sparse.com", validated=2, failed=0)

    results = evaluate_probation_sources(engine)
    assert results["reset"] == 1

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.status == SourceStatus.CANDIDATE
        assert src.active is False
        assert src.probation_start is None
        assert src.articles_validated == 0


def test_evaluate_skips_recent_probation(tmp_path):
    """Source still within probation window not evaluated."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    _make_probation_source(engine, "recent.com", validated=12, failed=0, days_ago=5)

    results = evaluate_probation_sources(engine)
    assert results["promoted"] == 0
    assert results["rejected"] == 0
    assert results["reset"] == 0


def test_evaluate_last_evaluated_set(tmp_path):
    """last_evaluated is set on all evaluated sources."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    sid = _make_probation_source(engine, "any.com", validated=12, failed=1)

    evaluate_probation_sources(engine)

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.last_evaluated is not None


# ── Bias inference (06_04) ─────────────────────────────────────────


def test_bias_inferred_on_promotion(tmp_path):
    """Promoted source gets bias label from perspective sentiment."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        src = Source(
            name="Lefty", url="lefty.com",
            status=SourceStatus.PROBATION, active=True,
            trust_score=0.1,
            probation_start=datetime.now(UTC) - timedelta(days=15),
            articles_validated=12, articles_failed=1,
        )
        session.add(src)
        session.commit()
        sid = src.id

        # Create cluster + article + perspectives with negative sentiment
        cluster = StoryCluster(headline="Test", article_count=2, status=StoryStatus.ANALYZED)
        session.add(cluster)
        session.commit()
        session.refresh(cluster)

        session.add(Article(
            cluster_id=cluster.id, source_id=sid,
            title="Left article", url="https://lefty.com/a",
        ))
        session.add(Perspective(
            cluster_id=cluster.id, source_id=sid,
            summary="Left framing", sentiment=-0.5,
        ))
        session.commit()

    evaluate_probation_sources(engine)

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.status == SourceStatus.TRUSTED
        assert src.bias_label == BiasLabel.LEFT


def test_bias_unknown_without_perspectives(tmp_path):
    """Promoted source with no perspectives gets UNKNOWN bias."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    sid = _make_probation_source(engine, "nopersp.com", validated=12, failed=1)

    evaluate_probation_sources(engine)

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.status == SourceStatus.TRUSTED
        assert src.bias_label == BiasLabel.UNKNOWN


def test_bias_center_for_neutral_sentiment(tmp_path):
    """Source with avg sentiment near 0 gets CENTER bias."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        src = Source(
            name="Center", url="center.com",
            status=SourceStatus.PROBATION, active=True,
            trust_score=0.1,
            probation_start=datetime.now(UTC) - timedelta(days=15),
            articles_validated=12, articles_failed=2,
        )
        session.add(src)
        session.commit()
        sid = src.id

        cluster = StoryCluster(headline="Test", article_count=1, status=StoryStatus.ANALYZED)
        session.add(cluster)
        session.commit()
        session.refresh(cluster)

        session.add(Article(
            cluster_id=cluster.id, source_id=sid,
            title="Neutral", url="https://center.com/a",
        ))
        session.add(Perspective(
            cluster_id=cluster.id, source_id=sid,
            summary="Neutral framing", sentiment=0.05,
        ))
        session.commit()

    evaluate_probation_sources(engine)

    with Session(engine) as session:
        src = session.get(Source, sid)
        assert src.bias_label == BiasLabel.CENTER


# ── Demotion (06_04) ───────────────────────────────────────────────


def test_demote_trusted_with_failures(tmp_path):
    """Trusted source with 5+ failures demoted to probation."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(
            name="Failing", url="failing.com",
            status=SourceStatus.TRUSTED,
            trust_score=0.5, articles_failed=5,
        ))
        session.commit()

    demoted = check_trusted_demotion(engine)
    assert demoted == 1

    with Session(engine) as session:
        src = session.exec(select(Source).where(Source.url == "failing.com")).first()
        assert src.status == SourceStatus.PROBATION
        assert src.trust_score == pytest.approx(0.1)
        assert src.probation_start is not None
        assert src.articles_validated == 0
        assert src.articles_failed == 0


def test_seed_never_demoted(tmp_path):
    """Seed sources immune to demotion."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(
            name="Reuters", url="reuters.com",
            status=SourceStatus.SEED,
            trust_score=0.95, articles_failed=100,
        ))
        session.commit()

    demoted = check_trusted_demotion(engine)
    assert demoted == 0

    with Session(engine) as session:
        src = session.exec(select(Source).where(Source.url == "reuters.com")).first()
        assert src.status == SourceStatus.SEED


def test_demote_below_threshold_not_demoted(tmp_path):
    """Trusted source with 4 failures (below threshold) not demoted."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(Source(
            name="OK", url="ok.com",
            status=SourceStatus.TRUSTED,
            trust_score=0.5, articles_failed=4,
        ))
        session.commit()

    demoted = check_trusted_demotion(engine)
    assert demoted == 0


# ── Scheduler job (06_04) ──────────────────────────────────────────


def test_scheduler_has_source_evaluation_job():
    """build_scheduler includes the source_evaluation cron job."""
    from unittest.mock import patch
    with patch("prism.main.settings") as mock_settings:
        mock_settings.discovery_interval_hours = 4
        mock_settings.briefing_schedule_cron = "0 7 * * *"
        mock_settings.perception_scan_interval_minutes = 15

        from prism.main import build_scheduler
        scheduler = build_scheduler()
        job_ids = {j.id for j in scheduler.get_jobs()}
        assert "source_evaluation" in job_ids
