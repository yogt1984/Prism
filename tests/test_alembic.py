"""T14.1: Alembic migration infrastructure tests."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlmodel import Session
from typer.testing import CliRunner

from prism.cli._fmt import set_json_mode
from prism.cli.app import app
from prism.db import _is_alembic_managed, init_db
from prism.models import Source, User

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    set_json_mode(False)
    yield
    set_json_mode(False)


@pytest.fixture()
def _reset_engine():
    """Save and restore the db module singleton around tests."""
    import prism.db
    original = prism.db._engine
    prism.db._engine = None
    yield
    # Dispose any engine created during the test to avoid leaked connections
    if prism.db._engine is not None and prism.db._engine is not original:
        try:
            prism.db._engine.dispose()
        except Exception:
            pass
    prism.db._engine = original


def _alembic_cfg(db_url: str) -> Config:
    """Build an Alembic Config pointing at the project root."""
    project_root = Path(__file__).resolve().parent.parent
    cfg = Config(str(project_root / "alembic.ini"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _make_engine(tmp_path: Path, name: str = "test.db"):
    url = f"sqlite:///{tmp_path / name}"
    return create_engine(url, connect_args={"check_same_thread": False}), url


# ══════════════════════════════════════════════════════════════════════
# Alembic upgrade / downgrade
# ══════════════════════════════════════════════════════════════════════


class TestAlembicMigrations:
    """Core migration lifecycle tests."""

    def test_upgrade_head_creates_all_tables(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        tables = set(inspect(eng).get_table_names())
        expected = {
            "source", "storycluster", "article", "perspective",
            "user", "engagement", "briefing", "topicresonance",
            "keywordtrack", "keywordmention", "perceptionsnapshot",
            "stripeevent", "alembic_version",
        }
        assert expected == tables
        eng.dispose()

    def test_upgrade_head_creates_source_columns(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        cols = {c["name"] for c in inspect(eng).get_columns("source")}
        expected = {"id", "name", "url", "rss_url", "trust_score",
                    "bias_label", "categories", "active", "created_at"}
        assert expected == cols
        eng.dispose()

    def test_upgrade_head_creates_user_columns(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        cols = {c["name"] for c in inspect(eng).get_columns("user")}
        assert "api_key_hash" in cols
        assert "email" in cols
        assert "is_pro" in cols
        eng.dispose()

    def test_upgrade_head_creates_storycluster_columns(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        cols = {c["name"] for c in inspect(eng).get_columns("storycluster")}
        expected = {"id", "headline", "summary", "categories", "status",
                    "article_count", "prompt_version", "quality_score",
                    "resonance_score", "first_seen", "last_updated"}
        assert expected == cols
        eng.dispose()

    def test_upgrade_creates_alembic_version(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        assert "alembic_version" in inspect(eng).get_table_names()
        with eng.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row is not None
            assert row[0] == "008"
        eng.dispose()

    def test_downgrade_base_drops_app_tables(self, tmp_path):
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        tables = inspect(eng).get_table_names()
        assert tables == ["alembic_version"]
        eng.dispose()

    def test_downgrade_then_upgrade_roundtrip(self, tmp_path):
        """upgrade → downgrade → upgrade must restore all tables."""
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")
        command.upgrade(cfg, "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        tables = set(inspect(eng).get_table_names())
        assert "source" in tables
        assert "user" in tables
        assert "alembic_version" in tables
        eng.dispose()

    def test_upgrade_is_idempotent(self, tmp_path):
        """Running upgrade head twice must not error."""
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "head")
        command.upgrade(cfg, "head")  # second run — should be no-op
        eng = create_engine(url, connect_args={"check_same_thread": False})
        assert "source" in inspect(eng).get_table_names()
        eng.dispose()

    def test_upgrade_head_no_data_loss(self, tmp_path):
        """Data inserted after migration survives a re-upgrade."""
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            conn.execute(text(
                "INSERT INTO source (name, url, created_at) "
                "VALUES ('TestSrc', 'test.com', '2026-01-01')"
            ))
            conn.commit()
        command.upgrade(cfg, "head")  # re-run
        with eng.connect() as conn:
            row = conn.execute(text("SELECT name FROM source")).fetchone()
            assert row is not None
            assert row[0] == "TestSrc"
        eng.dispose()

    def test_migration_creates_source_name_index(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        indexes = inspect(eng).get_indexes("source")
        idx_names = {idx["name"] for idx in indexes}
        assert "ix_source_name" in idx_names
        eng.dispose()

    def test_migration_creates_user_email_index(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        indexes = inspect(eng).get_indexes("user")
        idx_names = {idx["name"] for idx in indexes}
        assert "ix_user_email" in idx_names
        eng.dispose()

    def test_migration_creates_unique_constraints(self, tmp_path):
        """source.url and article.url must be unique."""
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            conn.execute(text(
                "INSERT INTO source (name, url, created_at) "
                "VALUES ('A', 'dup.com', '2026-01-01')"
            ))
            conn.commit()
            with pytest.raises(Exception):
                conn.execute(text(
                    "INSERT INTO source (name, url, created_at) "
                    "VALUES ('B', 'dup.com', '2026-01-01')"
                ))
        eng.dispose()

    def test_foreign_keys_enforced(self, tmp_path):
        """Article must reference a valid source_id."""
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        # Enable FK enforcement for SQLite
        with eng.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            with pytest.raises(Exception):
                conn.execute(text(
                    "INSERT INTO article (source_id, title, url, fetched_at) "
                    "VALUES (99999, 'Bad FK', 'bad.com/1', '2026-01-01')"
                ))
        eng.dispose()


# ══════════════════════════════════════════════════════════════════════
# init_db + Alembic interaction
# ══════════════════════════════════════════════════════════════════════


class TestInitDbAlembicInteraction:
    """Verify init_db detects Alembic and behaves correctly."""

    def test_fresh_db_not_alembic_managed(self, tmp_path, _reset_engine):
        url = f"sqlite:///{tmp_path / 'fresh.db'}"
        engine = init_db(url)
        assert not _is_alembic_managed(engine)
        engine.dispose()

    def test_alembic_db_is_managed(self, tmp_path, _reset_engine):
        url = f"sqlite:///{tmp_path / 'managed.db'}"
        command.upgrade(_alembic_cfg(url), "head")
        import prism.db
        prism.db._engine = None
        engine = init_db(url)
        assert _is_alembic_managed(engine)
        engine.dispose()

    def test_init_db_creates_tables_on_fresh(self, tmp_path, _reset_engine):
        url = f"sqlite:///{tmp_path / 'init.db'}"
        engine = init_db(url)
        tables = set(inspect(engine).get_table_names())
        assert "source" in tables
        assert "user" in tables
        assert "alembic_version" not in tables
        engine.dispose()

    def test_init_db_skips_on_alembic_managed(self, tmp_path, _reset_engine):
        """init_db on alembic-managed DB must not duplicate or error."""
        url = f"sqlite:///{tmp_path / 'skip.db'}"
        command.upgrade(_alembic_cfg(url), "head")
        import prism.db
        prism.db._engine = None
        engine = init_db(url)
        # Tables should still exist (not dropped)
        assert "source" in inspect(engine).get_table_names()
        engine.dispose()

    def test_init_db_preserves_alembic_data(self, tmp_path, _reset_engine):
        """init_db must not corrupt alembic_version after detection."""
        url = f"sqlite:///{tmp_path / 'preserve.db'}"
        command.upgrade(_alembic_cfg(url), "head")
        import prism.db
        prism.db._engine = None
        engine = init_db(url)
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row is not None
            assert row[0] == "008"
        engine.dispose()

    def test_schema_matches_between_init_db_and_alembic(self, tmp_path, _reset_engine):
        """Tables created by init_db and alembic should have the same columns."""
        # Via init_db
        url1 = f"sqlite:///{tmp_path / 'via_init.db'}"
        engine1 = init_db(url1)
        init_tables = {}
        for table in ["source", "storycluster", "article", "perspective",
                       "user", "engagement", "briefing"]:
            init_tables[table] = {c["name"] for c in inspect(engine1).get_columns(table)}
        engine1.dispose()

        # Via alembic
        url2 = f"sqlite:///{tmp_path / 'via_alembic.db'}"
        command.upgrade(_alembic_cfg(url2), "head")
        eng2 = create_engine(url2, connect_args={"check_same_thread": False})
        for table, expected_cols in init_tables.items():
            alembic_cols = {c["name"] for c in inspect(eng2).get_columns(table)}
            assert expected_cols == alembic_cols, (
                f"Column mismatch in {table}: "
                f"init_db={expected_cols}, alembic={alembic_cols}"
            )
        eng2.dispose()


# ══════════════════════════════════════════════════════════════════════
# CLI: prism db upgrade
# ══════════════════════════════════════════════════════════════════════


class TestCliDbUpgrade:
    """prism db upgrade CLI command tests."""

    def test_cli_upgrade_creates_tables(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'cli.db'}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        # Just ensure it connects (creates the file)
        with engine.connect():
            pass

        with patch("prism.cli.db_cmd._get_engine", return_value=engine):
            with patch("prism.cli.db_cmd._get_alembic_config") as mock_cfg:
                cfg = _alembic_cfg(url)
                mock_cfg.return_value = cfg
                result = runner.invoke(app, ["db", "upgrade"])
        assert result.exit_code == 0
        tables = set(inspect(engine).get_table_names())
        assert "source" in tables
        assert "alembic_version" in tables
        engine.dispose()

    def test_cli_upgrade_default_target_is_head(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'head.db'}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        with engine.connect():
            pass

        with patch("prism.cli.db_cmd._get_engine", return_value=engine):
            with patch("prism.cli.db_cmd._get_alembic_config") as mock_cfg:
                mock_cfg.return_value = _alembic_cfg(url)
                result = runner.invoke(app, ["db", "upgrade"])
        assert result.exit_code == 0
        with engine.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row is not None
            assert row[0] == "008"
        engine.dispose()

    def test_cli_upgrade_specific_revision(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'rev.db'}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        with engine.connect():
            pass

        with patch("prism.cli.db_cmd._get_engine", return_value=engine):
            with patch("prism.cli.db_cmd._get_alembic_config") as mock_cfg:
                mock_cfg.return_value = _alembic_cfg(url)
                result = runner.invoke(app, ["db", "upgrade", "001"])
        assert result.exit_code == 0
        engine.dispose()

    def test_cli_upgrade_json_output(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'json.db'}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        with engine.connect():
            pass

        with patch("prism.cli.db_cmd._get_engine", return_value=engine):
            with patch("prism.cli.db_cmd._get_alembic_config") as mock_cfg:
                mock_cfg.return_value = _alembic_cfg(url)
                result = runner.invoke(app, ["--json", "db", "upgrade"])
        assert result.exit_code == 0
        # Alembic logs may precede the JSON — find the JSON object
        output = result.output
        json_start = output.index("{")
        data = json.loads(output[json_start:])
        assert data["status"] == "ok"
        assert data["revision"] == "head"
        engine.dispose()

    def test_cli_upgrade_idempotent(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'idem.db'}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        with engine.connect():
            pass

        with patch("prism.cli.db_cmd._get_engine", return_value=engine):
            with patch("prism.cli.db_cmd._get_alembic_config") as mock_cfg:
                mock_cfg.return_value = _alembic_cfg(url)
                r1 = runner.invoke(app, ["db", "upgrade"])
                r2 = runner.invoke(app, ["db", "upgrade"])
        assert r1.exit_code == 0
        assert r2.exit_code == 0
        engine.dispose()

    def test_cli_upgrade_shows_success_message(self, tmp_path):
        url = f"sqlite:///{tmp_path / 'msg.db'}"
        engine = create_engine(url, connect_args={"check_same_thread": False})
        with engine.connect():
            pass

        with patch("prism.cli.db_cmd._get_engine", return_value=engine):
            with patch("prism.cli.db_cmd._get_alembic_config") as mock_cfg:
                mock_cfg.return_value = _alembic_cfg(url)
                result = runner.invoke(app, ["db", "upgrade"])
        assert result.exit_code == 0
        assert "applied" in result.output.lower() or "migration" in result.output.lower()
        engine.dispose()


# ══════════════════════════════════════════════════════════════════════
# Data compatibility
# ══════════════════════════════════════════════════════════════════════


class TestAlembicDataCompat:
    """Ensure migrated schema works with ORM operations."""

    def test_orm_insert_after_migration(self, tmp_path, _reset_engine):
        url = f"sqlite:///{tmp_path / 'orm.db'}"
        command.upgrade(_alembic_cfg(url), "head")
        import prism.db
        prism.db._engine = None
        engine = prism.db.get_engine(url)
        with Session(engine) as s:
            s.add(Source(name="Reuters", url="reuters.com", trust_score=0.95))
            s.add(User(email="test@test.com", interests="finance"))
            s.commit()
        with Session(engine) as s:
            from sqlmodel import select
            sources = list(s.exec(select(Source)).all())
            assert len(sources) == 1
            assert sources[0].name == "Reuters"
            users = list(s.exec(select(User)).all())
            assert len(users) == 1
        engine.dispose()

    def test_orm_query_after_migration(self, tmp_path, _reset_engine):
        url = f"sqlite:///{tmp_path / 'query.db'}"
        command.upgrade(_alembic_cfg(url), "head")
        import prism.db
        prism.db._engine = None
        engine = prism.db.get_engine(url)
        with Session(engine) as s:
            for i in range(5):
                s.add(Source(name=f"Src{i}", url=f"src{i}.com"))
            s.commit()
        with Session(engine) as s:
            from sqlmodel import select
            results = s.exec(select(Source).where(Source.name == "Src3")).all()
            assert len(results) == 1
            assert results[0].url == "src3.com"
        engine.dispose()

    def test_data_survives_upgrade_roundtrip(self, tmp_path, _reset_engine):
        """Insert data → downgrade → upgrade → data must survive? No — downgrade drops.
        But upgrade after fresh should work."""
        url = f"sqlite:///{tmp_path / 'survive.db'}"
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            conn.execute(text(
                "INSERT INTO source (name, url, created_at) "
                "VALUES ('Persist', 'persist.com', '2026-01-01')"
            ))
            conn.commit()
        # Re-upgrade (no-op) — data must survive
        command.upgrade(cfg, "head")
        with eng.connect() as conn:
            row = conn.execute(text("SELECT name FROM source WHERE url='persist.com'")).fetchone()
            assert row is not None
            assert row[0] == "Persist"
        eng.dispose()


# ══════════════════════════════════════════════════════════════════════
# T14.2: Datetime index migration (002)
# ══════════════════════════════════════════════════════════════════════


class TestDatetimeIndexMigration:
    """Tests for 002_add_datetime_indexes migration."""

    _INDEX_NAMES = {
        "storycluster": "ix_storycluster_first_seen",
        "article": "ix_article_fetched_at",
        "briefing": "ix_briefing_created_at",
        "engagement": "ix_engagement_created_at",
    }

    def test_upgrade_002_creates_all_indexes(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "002")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        for table, idx_name in self._INDEX_NAMES.items():
            indexes = {idx["name"] for idx in inspect(eng).get_indexes(table)}
            assert idx_name in indexes, f"Missing index {idx_name} on {table}"
        eng.dispose()

    def test_upgrade_002_index_columns(self, tmp_path):
        """Each index must cover the correct column."""
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "002")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        expected_cols = {
            "ix_storycluster_first_seen": ["first_seen"],
            "ix_article_fetched_at": ["fetched_at"],
            "ix_briefing_created_at": ["created_at"],
            "ix_engagement_created_at": ["created_at"],
        }
        for table, idx_name in self._INDEX_NAMES.items():
            indexes = inspect(eng).get_indexes(table)
            match = [idx for idx in indexes if idx["name"] == idx_name]
            assert match, f"Index {idx_name} not found"
            assert match[0]["column_names"] == expected_cols[idx_name]
        eng.dispose()

    def test_downgrade_002_removes_indexes(self, tmp_path):
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "002")
        command.downgrade(cfg, "001")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        for table, idx_name in self._INDEX_NAMES.items():
            indexes = {idx["name"] for idx in inspect(eng).get_indexes(table)}
            assert idx_name not in indexes, f"Index {idx_name} still exists after downgrade"
        # Verify we're back at revision 001
        with eng.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row[0] == "001"
        eng.dispose()

    def test_downgrade_002_preserves_tables(self, tmp_path):
        """Downgrading 002 must not drop any tables."""
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "002")
        command.downgrade(cfg, "001")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        tables = set(inspect(eng).get_table_names())
        for t in ("source", "storycluster", "article", "perspective",
                   "user", "engagement", "briefing"):
            assert t in tables, f"Table {t} missing after downgrade to 001"
        eng.dispose()

    def test_roundtrip_002_no_data_loss(self, tmp_path):
        """upgrade 002 → insert data → downgrade 001 → upgrade 002 — data survives."""
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "002")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            conn.execute(text(
                "INSERT INTO source (name, url, created_at) "
                "VALUES ('DataTest', 'data.com', '2026-01-01')"
            ))
            conn.execute(text(
                "INSERT INTO storycluster (headline, first_seen, last_updated) "
                "VALUES ('Test Story', '2026-01-15', '2026-01-15')"
            ))
            conn.commit()
        command.downgrade(cfg, "001")
        command.upgrade(cfg, "002")
        with eng.connect() as conn:
            row = conn.execute(text("SELECT name FROM source WHERE url='data.com'")).fetchone()
            assert row is not None and row[0] == "DataTest"
            row = conn.execute(text("SELECT headline FROM storycluster")).fetchone()
            assert row is not None and row[0] == "Test Story"
        eng.dispose()

    def test_stepwise_upgrade_001_then_002(self, tmp_path):
        """Upgrade to 001 first, then 002 — simulates incremental migration."""
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "001")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        # No datetime indexes at 001
        for table, idx_name in self._INDEX_NAMES.items():
            indexes = {idx["name"] for idx in inspect(eng).get_indexes(table)}
            assert idx_name not in indexes
        eng.dispose()
        # Now upgrade to 002
        command.upgrade(cfg, "002")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        for table, idx_name in self._INDEX_NAMES.items():
            indexes = {idx["name"] for idx in inspect(eng).get_indexes(table)}
            assert idx_name in indexes
        eng.dispose()

    def test_head_is_002(self, tmp_path):
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "head")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row[0] == "008"
        eng.dispose()

    def test_explain_query_plan_uses_index(self, tmp_path):
        """SQLite EXPLAIN QUERY PLAN should reference the index for filtered queries."""
        _, url = _make_engine(tmp_path)
        command.upgrade(_alembic_cfg(url), "002")
        eng = create_engine(url, connect_args={"check_same_thread": False})
        queries = {
            "ix_storycluster_first_seen": (
                "SELECT * FROM storycluster WHERE first_seen > '2026-01-01'"
            ),
            "ix_article_fetched_at": (
                "SELECT * FROM article WHERE fetched_at > '2026-01-01'"
            ),
            "ix_briefing_created_at": (
                "SELECT * FROM briefing WHERE created_at > '2026-01-01'"
            ),
            "ix_engagement_created_at": (
                "SELECT * FROM engagement WHERE created_at > '2026-01-01'"
            ),
        }
        with eng.connect() as conn:
            for idx_name, query in queries.items():
                plan = conn.execute(text(f"EXPLAIN QUERY PLAN {query}")).fetchall()
                plan_text = " ".join(str(row) for row in plan)
                assert idx_name in plan_text, (
                    f"Index {idx_name} not used in query plan: {plan_text}"
                )
        eng.dispose()

    def test_upgrade_002_idempotent(self, tmp_path):
        """Running upgrade to 002 twice must not error."""
        _, url = _make_engine(tmp_path)
        cfg = _alembic_cfg(url)
        command.upgrade(cfg, "002")
        command.upgrade(cfg, "002")  # no-op
        eng = create_engine(url, connect_args={"check_same_thread": False})
        with eng.connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version")).fetchone()
            assert row[0] == "002"
        eng.dispose()
