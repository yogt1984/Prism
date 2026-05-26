"""Alembic environment configuration for Prism.

Uses SQLModel metadata for autogenerate support and reads the database
URL from prism.config when available, falling back to alembic.ini.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

# Import all models so SQLModel.metadata has every table registered.
import prism.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = SQLModel.metadata


def _get_url() -> str:
    """Resolve database URL: alembic.ini (may be overridden by caller) > prism config."""
    # Prefer the URL from alembic config — callers (CLI, tests) set this explicitly.
    url = config.get_main_option("sqlalchemy.url")
    if url:
        return url
    try:
        from prism.config import get_settings
        return get_settings().database_url
    except Exception:
        return "sqlite:///data/newsgen.db"


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — emit SQL without a live connection."""
    context.configure(
        url=_get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations with a live database connection."""
    cfg = config.get_section(config.config_ini_section, {})
    cfg["sqlalchemy.url"] = _get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
