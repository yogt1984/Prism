"""SQLite backup via VACUUM INTO — consistent point-in-time copies."""

import logging
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import Engine, text

logger = logging.getLogger(__name__)


def backup_database(engine: Engine, dest_path: Path) -> Path:
    """Create a consistent backup using VACUUM INTO.

    This produces a standalone copy without locking the main database.
    Requires SQLite 3.27+ (Python 3.8+ bundles 3.31+).
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    start = time.monotonic()
    with engine.connect() as conn:
        conn.execute(text(f"VACUUM INTO '{dest_path}'"))

    elapsed = time.monotonic() - start
    size_mb = os.path.getsize(dest_path) / (1024 * 1024)
    logger.info("Backup created: %s (%.3f MB, %.2fs)", dest_path, size_mb, elapsed)
    return dest_path


def default_backup_path(data_dir: Path | None = None) -> Path:
    """Generate a timestamped backup filename."""
    base = data_dir or Path("data/backups")
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return base / f"prism-{ts}.db"


def rotate_backups(backup_dir: Path, keep: int) -> list[Path]:
    """Keep only the N most recent backups, delete older ones.

    Returns the list of deleted paths.
    """
    if not backup_dir.is_dir():
        return []

    backups = sorted(backup_dir.glob("prism-*.db"), key=lambda p: p.name)
    to_delete = backups[:-keep] if len(backups) > keep else []

    for path in to_delete:
        path.unlink()
        logger.info("Rotated old backup: %s", path)

    return to_delete
