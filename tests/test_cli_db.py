"""T10.1: prism db init|stats|export command tests."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session
from typer.testing import CliRunner

from prism.cli._fmt import set_json_mode
from prism.cli.app import app
from prism.db import init_db
from prism.models import (
    Article,
    Briefing,
    Engagement,
    Perspective,
    Source,
    StoryCluster,
    User,
)

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    set_json_mode(False)
    yield
    set_json_mode(False)


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


def _patch_engine(engine):
    return patch("prism.cli.db_cmd._get_engine", return_value=engine)


# ── init ──────────────────────────────────────────────────────────────

def test_db_init_creates_tables(db_engine):
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "init"])
    assert result.exit_code == 0


def test_db_init_json(db_engine):
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--json", "db", "init"])
    data = json.loads(result.output)
    assert data["status"] == "ok"


def test_db_init_idempotent(db_engine):
    """Calling init twice must not error or duplicate tables."""
    with _patch_engine(db_engine):
        r1 = runner.invoke(app, ["db", "init"])
        r2 = runner.invoke(app, ["db", "init"])
    assert r1.exit_code == 0
    assert r2.exit_code == 0


# ── stats ─────────────────────────────────────────────────────────────

def test_db_stats_all_tables(db_engine):
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "stats"])
    assert result.exit_code == 0
    assert "source" in result.output.lower()
    assert "article" in result.output.lower()


def test_db_stats_json(db_engine):
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--json", "db", "stats"])
    data = json.loads(result.output)
    assert "tables" in data
    assert "source" in data["tables"]
    assert "db_size_mb" in data


def test_db_stats_with_data(db_engine):
    with Session(db_engine) as s:
        s.add(Source(name="Test", url="test.com", trust_score=0.8))
        s.add(User(email="a@b.com", interests="finance"))
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--json", "db", "stats"])
    data = json.loads(result.output)
    assert data["tables"]["source"] == 1
    assert data["tables"]["user"] == 1
    assert data["tables"]["article"] == 0


def test_db_stats_reports_all_seven_tables(db_engine):
    """stats must report every known model table, even when empty."""
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--json", "db", "stats"])
    data = json.loads(result.output)
    expected = {"source", "storycluster", "article", "perspective",
                "user", "engagement", "briefing"}
    assert set(data["tables"].keys()) == expected


def test_db_stats_counts_are_integers(db_engine):
    """Row counts must be ints, not strings or floats."""
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--json", "db", "stats"])
    data = json.loads(result.output)
    for table, count in data["tables"].items():
        assert isinstance(count, int), f"{table} count is {type(count)}"


def test_db_stats_size_non_negative(db_engine):
    """DB size must be >= 0 even on a fresh database."""
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--json", "db", "stats"])
    data = json.loads(result.output)
    assert data["db_size_mb"] >= 0
    assert data["wal_size_mb"] >= 0


def test_db_stats_counts_update_after_insert(db_engine):
    """Verify counts reflect data added between calls."""
    with _patch_engine(db_engine):
        r1 = runner.invoke(app, ["--json", "db", "stats"])
    d1 = json.loads(r1.output)
    assert d1["tables"]["source"] == 0

    with Session(db_engine) as s:
        s.add(Source(name="AP", url="ap.org", trust_score=0.9))
        s.add(Source(name="BBC", url="bbc.co.uk", trust_score=0.85))
        s.commit()

    with _patch_engine(db_engine):
        r2 = runner.invoke(app, ["--json", "db", "stats"])
    d2 = json.loads(r2.output)
    assert d2["tables"]["source"] == 2


# ── export ────────────────────────────────────────────────────────────

def test_db_export_all(db_engine):
    with Session(db_engine) as s:
        s.add(Source(name="Reuters", url="reuters.com", trust_score=0.9))
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export"])
    data = json.loads(result.output)
    assert "source" in data
    assert len(data["source"]) == 1
    assert data["source"][0]["name"] == "Reuters"


def test_db_export_single_table(db_engine):
    with Session(db_engine) as s:
        s.add(Source(name="BBC", url="bbc.co.uk", trust_score=0.85))
        s.add(User(email="x@y.com", interests="tech"))
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "source"])
    data = json.loads(result.output)
    assert "source" in data
    assert "user" not in data
    assert len(data["source"]) == 1


def test_db_export_invalid_table(db_engine):
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "nonexistent"])
    assert result.exit_code == 1
    assert "Unknown table" in result.output


def test_db_export_empty_table(db_engine):
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "user"])
    data = json.loads(result.output)
    assert data["user"] == []


def test_db_export_table_name_case_insensitive(db_engine):
    """--table SOURCE should work the same as --table source."""
    with Session(db_engine) as s:
        s.add(Source(name="AP", url="ap.org", trust_score=0.9))
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "SOURCE"])
    data = json.loads(result.output)
    assert "source" in data
    assert len(data["source"]) == 1


def test_db_export_invalid_table_lists_valid_options(db_engine):
    """Error message must list the valid table names."""
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "bogus"])
    for valid_name in ("source", "article", "user", "briefing"):
        assert valid_name in result.output


def test_db_export_all_returns_all_tables(db_engine):
    """Export without --table must include every known table key."""
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export"])
    data = json.loads(result.output)
    expected = {"source", "storycluster", "article", "perspective",
                "user", "engagement", "briefing"}
    assert set(data.keys()) == expected


def test_db_export_output_is_valid_json(db_engine):
    """Guard against Rich console control chars or trailing garbage."""
    with Session(db_engine) as s:
        s.add(Source(name="CNN", url="cnn.com", trust_score=0.7))
        s.commit()
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export"])
    # Must parse without error — no trailing chars
    data = json.loads(result.output.strip())
    assert isinstance(data, dict)


def test_db_export_preserves_field_values(db_engine):
    """Exported rows must round-trip key field values exactly."""
    with Session(db_engine, expire_on_commit=False) as s:
        src = Source(name="Al Jazeera", url="aljazeera.com",
                     trust_score=0.65, bias_label="center", rss_url="feed.xml")
        s.add(src)
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "source"])
    row = json.loads(result.output)["source"][0]
    assert row["name"] == "Al Jazeera"
    assert row["url"] == "aljazeera.com"
    assert row["trust_score"] == 0.65
    assert row["bias_label"] == "center"
    assert row["rss_url"] == "feed.xml"


def test_db_export_multiple_rows_ordered(db_engine):
    """Multiple rows must all appear (order may vary, but count must match)."""
    with Session(db_engine) as s:
        for i in range(5):
            s.add(Source(name=f"Src{i}", url=f"src{i}.com", trust_score=0.5))
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "source"])
    data = json.loads(result.output)
    assert len(data["source"]) == 5


def test_db_export_datetime_serialisable(db_engine):
    """datetime fields must serialise to JSON (default=str handles this)."""
    with Session(db_engine) as s:
        s.add(User(email="dt@test.com", interests="finance"))
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export", "--table", "user"])
    row = json.loads(result.output)["user"][0]
    assert "created_at" in row
    # Must be a string, not crash during serialisation
    assert isinstance(row["created_at"], str)
    assert len(row["created_at"]) > 0


def test_db_export_with_foreign_key_data(db_engine):
    """Export must handle rows with FK relationships without crashing."""
    with Session(db_engine, expire_on_commit=False) as s:
        src = Source(name="NYT", url="nyt.com", trust_score=0.9)
        s.add(src)
        s.commit()
        cluster = StoryCluster(headline="Test Event", article_count=1)
        s.add(cluster)
        s.commit()
        art = Article(cluster_id=cluster.id, source_id=src.id,
                      title="Article 1", url="nyt.com/1", snippet="text")
        s.add(art)
        s.commit()

    with _patch_engine(db_engine):
        result = runner.invoke(app, ["db", "export"])
    data = json.loads(result.output)
    assert len(data["article"]) == 1
    assert data["article"][0]["cluster_id"] == cluster.id
    assert data["article"][0]["source_id"] == src.id


# ── quiet flag ────────────────────────────────────────────────────────

def test_db_init_quiet_suppresses_info(db_engine):
    """--quiet must suppress the 'Database initialised' message."""
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--quiet", "db", "init"])
    assert result.exit_code == 0
    assert "initialised" not in result.output.lower()


def test_db_stats_quiet_still_shows_table(db_engine):
    """--quiet suppresses info but stats table should still render."""
    with _patch_engine(db_engine):
        result = runner.invoke(app, ["--quiet", "db", "stats"])
    # Should still show something (table output)
    assert result.exit_code == 0
