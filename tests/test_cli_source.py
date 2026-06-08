"""Tests for 06_05: CLI source lifecycle commands."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlmodel import Session, SQLModel, create_engine, select
from typer.testing import CliRunner

from prism.cli.app import app as cli
from prism.models import Source, SourceStatus

runner = CliRunner()


def _engine(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)
    return engine


def _patch_engine(engine):
    return patch("prism.db.get_engine", return_value=engine)


# ── candidates ─────────────────────────────────────────────────────


def test_source_candidates_lists(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        s.add(Source(name="cand1", url="cand1.com", status=SourceStatus.CANDIDATE, sighting_count=5))
        s.add(Source(name="cand2", url="cand2.com", status=SourceStatus.CANDIDATE, sighting_count=2))
        s.commit()

    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "candidates"])
    assert result.exit_code == 0
    assert "cand1.com" in result.output
    assert "cand2.com" in result.output


def test_source_candidates_empty(tmp_path):
    engine = _engine(tmp_path)
    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "candidates"])
    assert result.exit_code == 0
    assert "No candidate" in result.output


# ── probation ──────────────────────────────────────────────────────


def test_source_probation_lists(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        s.add(Source(
            name="prob1", url="prob1.com", status=SourceStatus.PROBATION,
            articles_validated=8, articles_failed=2, trust_score=0.3,
            probation_start=datetime.now(UTC) - timedelta(days=5),
        ))
        s.commit()

    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "probation"])
    assert result.exit_code == 0
    assert "prob1.com" in result.output


def test_source_probation_empty(tmp_path):
    engine = _engine(tmp_path)
    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "probation"])
    assert result.exit_code == 0
    assert "No sources in probation" in result.output


# ── evaluate ───────────────────────────────────────────────────────


def test_source_evaluate(tmp_path):
    engine = _engine(tmp_path)
    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "evaluate"])
    assert result.exit_code == 0
    assert "Evaluation complete" in result.output


# ── promote ────────────────────────────────────────────────────────


def test_source_promote(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        s.add(Source(name="Cand", url="cand.com", status=SourceStatus.CANDIDATE))
        s.commit()

    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "promote", "1"])
    assert result.exit_code == 0
    assert "Promoted" in result.output

    with Session(engine) as s:
        src = s.get(Source, 1)
        assert src.status == SourceStatus.TRUSTED
        assert src.trust_score == 0.5
        assert src.active is True


def test_source_promote_seed_fails(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        s.add(Source(name="Reuters", url="reuters.com", status=SourceStatus.SEED))
        s.commit()

    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "promote", "1"])
    assert result.exit_code != 0
    assert "seed" in result.output.lower()


def test_source_promote_not_found(tmp_path):
    engine = _engine(tmp_path)
    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "promote", "999"])
    assert result.exit_code != 0
    assert "not found" in result.output.lower()


# ── reject ─────────────────────────────────────────────────────────


def test_source_reject(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        s.add(Source(name="Bad", url="bad.com", status=SourceStatus.CANDIDATE))
        s.commit()

    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "reject", "1", "--reason", "Unreliable"])
    assert result.exit_code == 0
    assert "Rejected" in result.output

    with Session(engine) as s:
        src = s.get(Source, 1)
        assert src.status == SourceStatus.REJECTED
        assert src.rejection_reason == "Unreliable"


def test_source_reject_seed_fails(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        s.add(Source(name="AP", url="ap.com", status=SourceStatus.SEED))
        s.commit()

    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "reject", "1", "--reason", "test"])
    assert result.exit_code != 0
    assert "seed" in result.output.lower()


def test_source_reject_no_reason(tmp_path):
    engine = _engine(tmp_path)
    with Session(engine) as s:
        s.add(Source(name="X", url="x.com", status=SourceStatus.CANDIDATE))
        s.commit()

    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "reject", "1"])
    assert result.exit_code != 0
    assert "reason" in result.output.lower()


# ── blocklist ──────────────────────────────────────────────────────


def test_blocklist_ls(tmp_path):
    import prism.agents.blocklist as bl_mod
    bl_mod._blocklist = None
    f = tmp_path / "blocklist.txt"
    f.write_text("reddit.com\ntwitter.com\n")
    bl_mod.load_blocklist(f)

    engine = _engine(tmp_path)
    with _patch_engine(engine):
        result = runner.invoke(cli, ["source", "blocklist", "ls"])
    assert result.exit_code == 0
    assert "reddit.com" in result.output
    assert "twitter.com" in result.output
    assert "2 domains blocked" in result.output

    bl_mod._blocklist = None
