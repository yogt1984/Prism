"""Tests for 03_01: TTS schema, config, dependencies, and circuit breaker."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key, BriefingOut
from prism.db import init_db
from prism.models import Briefing, User


# ── Fixtures ─────────────────────────────────────────────────────────

_auth_state: dict = {"user": None}


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(db_engine):
    with Session(db_engine) as session:
        yield session


@pytest.fixture()
def client(db_engine):
    app = create_app()
    _auth_state["user"] = None

    def _override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[_get_session] = _override
    app.dependency_overrides[require_api_key] = lambda: _auth_state["user"]
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Briefing Model: audio field defaults ─────────────────────────────


def test_briefing_audio_fields_default_empty():
    b = Briefing(user_id=1)
    assert b.audio_path == ""
    assert b.audio_duration_sec == 0
    assert b.audio_size_bytes == 0


def test_briefing_audio_fields_set():
    b = Briefing(
        user_id=1,
        audio_path="audio/42.mp3",
        audio_duration_sec=180,
        audio_size_bytes=2_500_000,
    )
    assert b.audio_path == "audio/42.mp3"
    assert b.audio_duration_sec == 180
    assert b.audio_size_bytes == 2_500_000


def test_briefing_audio_fields_persist(tmp_path):
    """Audio fields survive a DB roundtrip."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        b = Briefing(
            user_id=1,
            content_text="hello",
            audio_path="audio/99.mp3",
            audio_duration_sec=300,
            audio_size_bytes=5_000_000,
        )
        session.add(b)
        session.commit()
        bid = b.id

    with Session(engine) as session:
        loaded = session.get(Briefing, bid)
        assert loaded is not None
        assert loaded.audio_path == "audio/99.mp3"
        assert loaded.audio_duration_sec == 300
        assert loaded.audio_size_bytes == 5_000_000
        assert loaded.content_text == "hello"


def test_briefing_existing_fields_preserved(tmp_path):
    """Creating a briefing without audio fields keeps existing fields."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        b = Briefing(user_id=1, content_html="<p>hi</p>", story_count=5)
        session.add(b)
        session.commit()
        bid = b.id

    with Session(engine) as session:
        loaded = session.get(Briefing, bid)
        assert loaded.content_html == "<p>hi</p>"
        assert loaded.story_count == 5
        assert loaded.audio_path == ""
        assert loaded.audio_duration_sec == 0


# ── Config: TTS settings ─────────────────────────────────────────────


def test_tts_config_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None
    s = cfg.Settings()  # type: ignore[call-arg]
    assert s.openai_api_key == ""
    assert s.tts_voice == "alloy"
    assert s.tts_model == "tts-1-hd"
    assert s.tts_max_chars == 50000
    assert s.tts_chunk_size == 4000
    assert s.audio_storage_dir == "data/audio"
    cfg._settings = None


def test_tts_config_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-test")
    monkeypatch.setenv("TTS_VOICE", "nova")
    monkeypatch.setenv("TTS_MODEL", "tts-1")
    monkeypatch.setenv("TTS_MAX_CHARS", "30000")
    monkeypatch.setenv("TTS_CHUNK_SIZE", "3000")
    monkeypatch.setenv("AUDIO_STORAGE_DIR", "/tmp/audio")
    import prism.config as cfg
    cfg._settings = None
    s = cfg.Settings()  # type: ignore[call-arg]
    assert s.openai_api_key == "sk-openai-test"
    assert s.tts_voice == "nova"
    assert s.tts_model == "tts-1"
    assert s.tts_max_chars == 30000
    assert s.tts_chunk_size == 3000
    assert s.audio_storage_dir == "/tmp/audio"
    cfg._settings = None


def test_tts_config_no_crash_without_openai_key(monkeypatch):
    """App starts without OPENAI_API_KEY set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    import prism.config as cfg
    cfg._settings = None
    s = cfg.Settings()  # type: ignore[call-arg]
    assert s.openai_api_key == ""
    cfg._settings = None


# ── Circuit Breaker ───────────────────────────────────────────────────


def test_openai_tts_breaker_exists():
    from prism.circuit_breaker import openai_tts_breaker
    assert openai_tts_breaker.name == "openai_tts"


def test_openai_tts_breaker_independent():
    """Tripping openai_tts_breaker does not affect claude_breaker."""
    from prism.circuit_breaker import (
        CircuitState,
        claude_breaker,
        openai_tts_breaker,
    )

    openai_tts_breaker.reset()
    claude_breaker.reset()

    for _ in range(5):
        openai_tts_breaker.record_failure()

    assert openai_tts_breaker.state == CircuitState.OPEN
    assert claude_breaker.state == CircuitState.CLOSED

    openai_tts_breaker.reset()


def test_openai_tts_breaker_recovery():
    """Breaker recovers after success in half-open state."""
    from prism.circuit_breaker import CircuitState, openai_tts_breaker

    openai_tts_breaker.reset()

    for _ in range(5):
        openai_tts_breaker.record_failure()
    assert openai_tts_breaker.state == CircuitState.OPEN

    # Force half-open by manipulating last failure time
    openai_tts_breaker._last_failure_time -= 301
    assert openai_tts_breaker.state == CircuitState.HALF_OPEN

    openai_tts_breaker.record_success()
    assert openai_tts_breaker.state == CircuitState.CLOSED

    openai_tts_breaker.reset()


# ── Audio Storage Directory ───────────────────────────────────────────


def test_init_db_creates_audio_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("AUDIO_STORAGE_DIR", str(tmp_path / "audio"))
    import prism.config as cfg
    cfg._settings = None

    import prism.db as db_mod
    db_mod._engine = None
    init_db(f"sqlite:///{tmp_path / 'test.db'}")

    assert (tmp_path / "audio").is_dir()

    cfg._settings = None
    db_mod._engine = None


# ── BriefingOut Schema ────────────────────────────────────────────────


def test_briefingout_has_audio_true():
    """BriefingOut derives has_audio=True when audio_path is set."""
    b = Briefing(
        id=1, user_id=1, audio_path="audio/1.mp3",
        audio_duration_sec=120, audio_size_bytes=1_000_000,
    )
    out = BriefingOut.model_validate(b, from_attributes=True)
    assert out.has_audio is True
    assert out.audio_duration_sec == 120
    assert out.audio_size_bytes == 1_000_000


def test_briefingout_has_audio_false():
    """BriefingOut derives has_audio=False when audio_path is empty."""
    b = Briefing(id=1, user_id=1)
    out = BriefingOut.model_validate(b, from_attributes=True)
    assert out.has_audio is False
    assert out.audio_duration_sec == 0
    assert out.audio_size_bytes == 0


def test_briefingout_does_not_expose_audio_path():
    """audio_path must not appear in the serialized output."""
    b = Briefing(id=1, user_id=1, audio_path="audio/1.mp3")
    out = BriefingOut.model_validate(b, from_attributes=True)
    data = out.model_dump()
    assert "audio_path" not in data


# ── API: Briefing response includes new fields ───────────────────────


def test_api_briefing_response_has_audio_fields(client, db_engine):
    """GET /users/{id}/briefings includes audio fields."""
    with Session(db_engine) as session:
        user = User(email="test@test.com", is_pro=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        uid = user.id

        b = Briefing(user_id=uid, story_count=3)
        session.add(b)
        session.commit()

    _auth_state["user"] = User(id=uid, email="test@test.com", is_pro=True)
    resp = client.get(f"/users/{uid}/briefings")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert "has_audio" in data[0]
    assert "audio_duration_sec" in data[0]
    assert "audio_size_bytes" in data[0]
    assert data[0]["has_audio"] is False
    assert "audio_path" not in data[0]


# ── Metrics ───────────────────────────────────────────────────────────


def test_tts_metrics_exist():
    from prism.metrics import (
        tts_chars_processed_total,
        tts_duration_seconds,
        tts_failed_total,
        tts_generated_total,
    )
    assert tts_generated_total.name == "tts_generated_total"
    assert tts_failed_total.name == "tts_failed_total"
    assert tts_duration_seconds.name == "tts_duration_seconds"
    assert tts_chars_processed_total.name == "tts_chars_processed_total"


def test_tts_metrics_in_snapshot():
    from prism.metrics import snapshot
    snap = snapshot()
    assert "tts_generated_total" in snap
    assert "tts_failed_total" in snap
    assert "tts_duration_seconds" in snap
    assert "tts_chars_processed_total" in snap


# ── Alembic Migration ────────────────────────────────────────────────


def test_alembic_head_is_008(tmp_path):
    """Verify Alembic head revision is 008."""
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{tmp_path / 'test.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")

    from sqlalchemy import create_engine as sa_create_engine, text
    engine = sa_create_engine(url)
    with engine.connect() as conn:
        rev = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    assert rev == "008"


def test_alembic_008_adds_audio_columns(tmp_path):
    """Migration 008 adds audio columns to briefing table."""
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{tmp_path / 'test.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")

    from sqlalchemy import create_engine as sa_create_engine, inspect as sa_inspect
    engine = sa_create_engine(url)
    insp = sa_inspect(engine)
    cols = {c["name"] for c in insp.get_columns("briefing")}
    assert "audio_path" in cols
    assert "audio_duration_sec" in cols
    assert "audio_size_bytes" in cols


def test_alembic_008_downgrade(tmp_path):
    """Downgrade from 008 removes audio columns."""
    from alembic import command
    from alembic.config import Config

    url = f"sqlite:///{tmp_path / 'test.db'}"
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "007")

    from sqlalchemy import create_engine as sa_create_engine, inspect as sa_inspect
    engine = sa_create_engine(url)
    insp = sa_inspect(engine)
    cols = {c["name"] for c in insp.get_columns("briefing")}
    assert "audio_path" not in cols
    assert "audio_duration_sec" not in cols
    assert "audio_size_bytes" not in cols
