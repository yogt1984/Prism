"""prism db — database management commands."""

import json as _json
import os
from pathlib import Path
from typing import Annotated

import typer
from sqlmodel import Session, select

from prism.cli._fmt import (
    cli_get_engine as _get_engine,
)
from prism.cli._fmt import (
    console,
    err_console,
    info,
    is_json_mode,
    print_json,
    print_table,
)

app = typer.Typer(help="Database management.")


@app.command("upgrade")
def db_upgrade(
    revision: Annotated[
        str,
        typer.Argument(help="Target revision (default: head)."),
    ] = "head",
) -> None:
    """Run Alembic migrations up to the target revision."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = _get_alembic_config()
    try:
        command.upgrade(alembic_cfg, revision)
    except Exception as exc:
        err_console.print(f"[red]Migration failed:[/red] {exc}")
        raise typer.Exit(1)

    if is_json_mode():
        print_json({"status": "ok", "revision": revision})
        return
    info(f"  [green]Migrations applied[/green] (target: {revision})")


def _get_alembic_config():  # type: ignore[no-untyped-def]
    """Build an Alembic Config pointing at the project's alembic directory."""
    import pathlib

    from alembic.config import Config

    # alembic.ini lives at the project root
    project_root = pathlib.Path(__file__).resolve().parent.parent.parent.parent
    ini_path = project_root / "alembic.ini"
    cfg = Config(str(ini_path))

    # Override the database URL from prism settings or CLI --db flag
    engine = _get_engine()
    cfg.set_main_option(
        "sqlalchemy.url",
        engine.url.render_as_string(hide_password=False),
    )
    return cfg

_TABLE_MODELS = {
    "source": "Source",
    "storycluster": "StoryCluster",
    "article": "Article",
    "perspective": "Perspective",
    "user": "User",
    "engagement": "Engagement",
    "briefing": "Briefing",
}


def _get_model(name: str):  # type: ignore[no-untyped-def]
    """Import and return a model class by table name."""
    import prism.models as models
    class_name = _TABLE_MODELS.get(name.lower())
    if class_name is None:
        return None
    return getattr(models, class_name, None)


@app.command("init")
def db_init() -> None:
    """Initialise the database (create tables if missing)."""
    from prism.db import init_db

    engine = _get_engine()
    init_db(engine.url.render_as_string(hide_password=False))
    info("  [green]Database initialised[/green]")

    if is_json_mode():
        print_json({"status": "ok"})


@app.command("stats")
def db_stats() -> None:
    """Show row counts and database file size."""
    engine = _get_engine()
    counts: dict[str, int] = {}
    with Session(engine) as session:
        for table_name, class_name in _TABLE_MODELS.items():
            model = _get_model(table_name)
            if model:
                counts[table_name] = len(session.exec(select(model)).all())

    # File size (works for SQLite file:// URLs)
    db_url = str(engine.url)
    db_size_mb = 0.0
    wal_size_mb = 0.0
    if "sqlite" in db_url:
        path = db_url.split("///")[-1]
        if os.path.isfile(path):
            db_size_mb = os.path.getsize(path) / (1024 * 1024)
        wal_path = path + "-wal"
        if os.path.isfile(wal_path):
            wal_size_mb = os.path.getsize(wal_path) / (1024 * 1024)

    if is_json_mode():
        print_json({
            "tables": counts,
            "db_size_mb": round(db_size_mb, 3),
            "wal_size_mb": round(wal_size_mb, 3),
        })
        return

    rows = [[name, str(count)] for name, count in counts.items()]
    print_table("Database Stats", ["Table", "Rows"], rows)
    console.print(f"\n  DB size: {db_size_mb:.3f} MB  |  WAL: {wal_size_mb:.3f} MB")


@app.command("export")
def db_export(
    table: Annotated[
        str | None,
        typer.Option("--table", "-t", help="Export a single table (e.g. source, article)."),
    ] = None,
) -> None:
    """Export all or one table as JSON to stdout."""
    engine = _get_engine()

    if table and table.lower() not in _TABLE_MODELS:
        valid = ", ".join(sorted(_TABLE_MODELS))
        err_console.print(f"[red]Unknown table:[/red] {table}. Valid: {valid}")
        raise typer.Exit(1)

    tables_to_export = [table.lower()] if table else list(_TABLE_MODELS)
    result: dict[str, list[dict]] = {}

    with Session(engine) as session:
        for tbl in tables_to_export:
            model = _get_model(tbl)
            if not model:
                continue
            rows = session.exec(select(model)).all()
            result[tbl] = [
                {k: v for k, v in r.model_dump().items()} for r in rows
            ]

    # Always output JSON (this is a data export command)
    print(_json.dumps(result, indent=2, default=str))


@app.command("backup")
def db_backup(
    dest: Annotated[
        str | None,
        typer.Option("--dest", "-d", help="Destination path for backup file."),
    ] = None,
    rotate: Annotated[
        int | None,
        typer.Option("--rotate", "-r", help="Keep only the N most recent backups."),
    ] = None,
) -> None:
    """Create a consistent backup of the SQLite database."""
    from prism.backup import backup_database, default_backup_path, rotate_backups

    engine = _get_engine()

    if dest:
        backup_path = Path(dest)
    else:
        backup_path = default_backup_path()

    try:
        result = backup_database(engine, backup_path)
    except Exception as exc:
        err_console.print(f"[red]Backup failed:[/red] {exc}")
        raise typer.Exit(1)

    size_mb = os.path.getsize(result) / (1024 * 1024)

    if rotate and rotate > 0:
        backup_dir = result.parent
        deleted = rotate_backups(backup_dir, rotate)
        rotate_info = f", rotated {len(deleted)} old backup(s)" if deleted else ""
    else:
        rotate_info = ""

    if is_json_mode():
        print_json({
            "status": "ok",
            "path": str(result),
            "size_mb": round(size_mb, 3),
        })
        return

    info(f"  [green]Backup created:[/green] {result} ({size_mb:.3f} MB{rotate_info})")
