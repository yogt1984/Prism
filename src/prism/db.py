from sqlalchemy import Engine, event
from sqlmodel import Session, SQLModel, create_engine

_engine: Engine | None = None


def _apply_sqlite_pragmas(engine: Engine) -> None:
    @event.listens_for(engine, "connect")
    def _set_pragmas(dbapi_conn, connection_record):  # type: ignore[no-untyped-def]
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def get_engine(url: str | None = None) -> Engine:
    """Get or create the SQLAlchemy engine. Pass url to override (useful for tests)."""
    global _engine
    if _engine is None or url is not None:
        if url is None:
            from prism.config import settings
            url = settings.database_url
        _engine = create_engine(
            url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
        _apply_sqlite_pragmas(_engine)
    return _engine


def init_db(url: str | None = None) -> Engine:
    """Create all tables. Returns the engine."""
    engine = get_engine(url)
    SQLModel.metadata.create_all(engine)
    return engine


def get_session(engine: Engine | None = None) -> Session:
    return Session(engine or get_engine())
