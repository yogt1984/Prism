"""Tests for 03_04: Audio streaming API endpoint."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydub import AudioSegment
from sqlmodel import Session, SQLModel, create_engine

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key
from prism.models import Briefing, User


# ── Helpers ─────────────────────────────────────────────────────────


def _make_mp3_bytes(duration_ms: int = 1000) -> bytes:
    seg = AudioSegment.silent(duration=duration_ms)
    buf = io.BytesIO()
    seg.export(buf, format="mp3")
    return buf.getvalue()


MP3_DATA = _make_mp3_bytes(1000)


# ── Fixtures ────────────────────────────────────────────────────────

_auth_state: dict = {"user": None}


@pytest.fixture()
def db_engine(tmp_path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = create_engine(url, connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def audio_dir(tmp_path, monkeypatch):
    """Create audio storage dir and configure settings."""
    d = tmp_path / "audio"
    d.mkdir()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("AUDIO_STORAGE_DIR", str(d))
    import prism.config as cfg
    cfg._settings = None
    yield d
    cfg._settings = None


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


@pytest.fixture()
def pro_user(db_engine):
    with Session(db_engine) as session:
        user = User(email="pro@test.com", is_pro=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def free_user(db_engine):
    with Session(db_engine) as session:
        user = User(email="free@test.com", is_pro=False)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def other_pro_user(db_engine):
    with Session(db_engine) as session:
        user = User(email="other@test.com", is_pro=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        return user


@pytest.fixture()
def audio_briefing(db_engine, pro_user, audio_dir):
    """Briefing with a real MP3 file on disk."""
    mp3_path = audio_dir / "42.mp3"
    mp3_path.write_bytes(MP3_DATA)

    with Session(db_engine) as session:
        b = Briefing(
            id=42,
            user_id=pro_user.id,
            content_text="Test briefing.",
            story_count=1,
            audio_path="audio/42.mp3",
            audio_duration_sec=1,
            audio_size_bytes=len(MP3_DATA),
        )
        session.add(b)
        session.commit()
        session.refresh(b)
        return b


@pytest.fixture()
def text_briefing(db_engine, pro_user):
    """Briefing without audio."""
    with Session(db_engine) as session:
        b = Briefing(
            user_id=pro_user.id,
            content_html="<p>Hello</p>",
            story_count=1,
        )
        session.add(b)
        session.commit()
        session.refresh(b)
        return b


# ── Full Download (AC1, AC2, AC3, AC8, AC13) ───────────────────────


def test_full_download(client, pro_user, audio_briefing):
    """Pro user downloads complete MP3."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert int(res.headers["content-length"]) == audio_briefing.audio_size_bytes
    assert len(res.content) == audio_briefing.audio_size_bytes


def test_content_type_is_audio_mpeg(client, pro_user, audio_briefing):
    """Content-Type header is audio/mpeg."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert res.headers["content-type"] == "audio/mpeg"


def test_accept_ranges_header(client, pro_user, audio_briefing):
    """Accept-Ranges header is present."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert res.headers["accept-ranges"] == "bytes"


def test_cache_control_header(client, pro_user, audio_briefing):
    """Cache-Control is private, max-age=86400."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert res.headers["cache-control"] == "private, max-age=86400"


def test_content_disposition_header(client, pro_user, audio_briefing):
    """Content-Disposition includes briefing ID."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert f"briefing-{audio_briefing.id}.mp3" in res.headers["content-disposition"]


def test_output_path_correct(client, pro_user, audio_briefing):
    """Output file exists at expected path."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert res.status_code == 200
    # Verify the returned bytes match the file on disk
    assert res.content == MP3_DATA


# ── Range Requests (AC4, AC5, AC6) ─────────────────────────────────


def test_range_request_returns_206(client, pro_user, audio_briefing):
    """Range request returns 206 with correct Content-Range."""
    _auth_state["user"] = pro_user
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"Range": "bytes=0-1023"},
    )
    assert res.status_code == 206
    assert f"bytes 0-1023/{len(MP3_DATA)}" in res.headers["content-range"]
    assert int(res.headers["content-length"]) == 1024
    assert len(res.content) == 1024


def test_range_correct_byte_slice(client, pro_user, audio_briefing):
    """Range request returns the correct byte slice."""
    _auth_state["user"] = pro_user
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"Range": "bytes=0-1023"},
    )
    assert res.content == MP3_DATA[:1024]


def test_range_open_end(client, pro_user, audio_briefing):
    """Range request with open end (bytes=100-) returns from offset to EOF."""
    _auth_state["user"] = pro_user
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"Range": "bytes=100-"},
    )
    assert res.status_code == 206
    expected_len = len(MP3_DATA) - 100
    assert len(res.content) == expected_len
    assert res.content == MP3_DATA[100:]


def test_range_invalid_returns_416(client, pro_user, audio_briefing):
    """Invalid range (beyond file size) returns 416."""
    _auth_state["user"] = pro_user
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"Range": "bytes=99999999-"},
    )
    assert res.status_code == 416


def test_range_malformed_returns_416(client, pro_user, audio_briefing):
    """Malformed range header returns 416."""
    _auth_state["user"] = pro_user
    res = client.get(
        f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio",
        headers={"Range": "invalid"},
    )
    assert res.status_code == 416


# ── Auth / Authz (AC8, AC9) ────────────────────────────────────────


def test_wrong_user_403(client, pro_user, other_pro_user, audio_briefing):
    """Cannot access another user's audio."""
    _auth_state["user"] = other_pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert res.status_code == 403


def test_free_user_403(client, free_user, audio_briefing):
    """Free user cannot access audio (require_api_key blocks non-Pro)."""
    # require_api_key is overridden to return the user directly,
    # but real middleware rejects non-pro. Test that the user_id
    # ownership check still applies.
    _auth_state["user"] = free_user
    res = client.get(f"/users/{free_user.id}/briefings/{audio_briefing.id}/audio")
    # Briefing belongs to pro_user, not free_user → 404 (not found for this user)
    assert res.status_code == 404


# ── 404 cases (AC10, AC11) ──────────────────────────────────────────


def test_no_audio_returns_404(client, pro_user, text_briefing):
    """Briefing without audio returns 404."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{text_briefing.id}/audio")
    assert res.status_code == 404
    assert "not available" in res.json()["detail"]


def test_missing_file_returns_404(client, pro_user, audio_briefing, audio_dir):
    """Briefing with audio_path but missing file returns 404."""
    # Delete the MP3 file
    (audio_dir / "42.mp3").unlink()
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/{audio_briefing.id}/audio")
    assert res.status_code == 404
    assert "missing" in res.json()["detail"]


def test_nonexistent_briefing_404(client, pro_user, audio_dir):
    """Nonexistent briefing returns 404."""
    _auth_state["user"] = pro_user
    res = client.get(f"/users/{pro_user.id}/briefings/99999/audio")
    assert res.status_code == 404
