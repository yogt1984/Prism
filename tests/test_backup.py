"""T19.5: SQLite backup and rotation tests."""

import sqlite3
import threading
from pathlib import Path

import pytest
from sqlmodel import Session, select

from prism.backup import backup_database, default_backup_path, rotate_backups
from prism.db import init_db
from prism.models import Source


@pytest.fixture()
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    # Seed a row so we can verify backup has data
    with Session(engine) as s:
        s.add(Source(name="Reuters", url="reuters.com", trust_score=0.9))
        s.commit()
    yield engine
    engine.dispose()


class TestBackupDatabase:

    def test_backup_creates_valid_sqlite(self, db_engine, tmp_path):
        dest = tmp_path / "backup.db"
        result = backup_database(db_engine, dest)
        assert result.exists()
        # Open independently and verify it's a valid SQLite DB
        conn = sqlite3.connect(str(result))
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "source" in table_names
        conn.close()

    def test_backup_contains_data(self, db_engine, tmp_path):
        dest = tmp_path / "backup.db"
        backup_database(db_engine, dest)
        conn = sqlite3.connect(str(dest))
        rows = conn.execute("SELECT COUNT(*) FROM source").fetchone()[0]
        assert rows == 1
        conn.close()

    def test_backup_creates_parent_dirs(self, db_engine, tmp_path):
        dest = tmp_path / "deep" / "nested" / "backup.db"
        result = backup_database(db_engine, dest)
        assert result.exists()

    def test_backup_does_not_lock_main_db(self, db_engine, tmp_path):
        """Concurrent reads/writes should succeed during backup."""
        dest = tmp_path / "backup.db"
        errors = []

        def reader():
            try:
                with Session(db_engine) as s:
                    s.exec(select(Source)).all()
            except Exception as e:
                errors.append(e)

        t = threading.Thread(target=reader)
        t.start()
        backup_database(db_engine, dest)
        t.join()

        assert not errors, f"Concurrent read failed: {errors}"

    def test_backup_file_size_nonzero(self, db_engine, tmp_path):
        dest = tmp_path / "backup.db"
        backup_database(db_engine, dest)
        assert dest.stat().st_size > 0


class TestDefaultBackupPath:

    def test_returns_path_with_timestamp(self):
        p = default_backup_path()
        assert p.name.startswith("prism-")
        assert p.name.endswith(".db")
        assert p.parent == Path("data/backups")

    def test_custom_data_dir(self, tmp_path):
        p = default_backup_path(tmp_path / "custom")
        assert p.parent == tmp_path / "custom"


class TestRotateBackups:

    def test_rotate_keeps_n_most_recent(self, tmp_path):
        # Create 5 fake backups with ordered names
        for i in range(5):
            (tmp_path / f"prism-2026050{i}-120000.db").touch()

        deleted = rotate_backups(tmp_path, keep=3)
        assert len(deleted) == 2
        remaining = sorted(tmp_path.glob("prism-*.db"))
        assert len(remaining) == 3
        # Oldest two should be gone
        assert "20260500" not in str(remaining[0])

    def test_rotate_noop_when_under_limit(self, tmp_path):
        (tmp_path / "prism-20260501-120000.db").touch()
        deleted = rotate_backups(tmp_path, keep=5)
        assert len(deleted) == 0
        assert len(list(tmp_path.glob("prism-*.db"))) == 1

    def test_rotate_empty_dir(self, tmp_path):
        deleted = rotate_backups(tmp_path, keep=3)
        assert len(deleted) == 0

    def test_rotate_nonexistent_dir(self, tmp_path):
        deleted = rotate_backups(tmp_path / "nonexistent", keep=3)
        assert len(deleted) == 0
