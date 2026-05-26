"""T10.7: API key authentication tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session, generate_api_key, hash_api_key
from prism.db import init_db
from prism.models import User


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    app = create_app()

    def _override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[_get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_pro_user(engine, email="pro@test.com"):
    raw_key, key_hash = generate_api_key()
    with Session(engine, expire_on_commit=False) as s:
        user = User(email=email, interests="finance", is_pro=True, api_key_hash=key_hash)
        s.add(user)
        s.commit()
    return user, raw_key


def _make_free_user(engine, email="free@test.com"):
    raw_key, key_hash = generate_api_key()
    with Session(engine, expire_on_commit=False) as s:
        user = User(email=email, interests="finance", is_pro=False, api_key_hash=key_hash)
        s.add(user)
        s.commit()
    return user, raw_key


# ── Public endpoints stay public ─────────────────────────────────────


def test_health_no_auth_required(client):
    resp = client.get("/health")
    assert resp.status_code == 200


def test_config_no_auth_required(client, db_engine):
    from unittest.mock import patch
    from prism.config import Settings

    fake = Settings(anthropic_api_key="sk-test")
    with patch("prism.config.get_settings", return_value=fake):
        resp = client.get("/config")
    assert resp.status_code == 200


def test_sources_no_auth_required(client):
    resp = client.get("/sources")
    assert resp.status_code == 200


def test_stories_no_auth_required(client):
    resp = client.get("/stories")
    assert resp.status_code == 200


def test_post_users_no_auth_required(client):
    """Registration must be public — no API key needed."""
    resp = client.post("/users", json={
        "email": "new@test.com", "interests": "finance",
    })
    assert resp.status_code == 201


# ── Missing API key → 401 ───────────────────────────────────────────


def test_get_user_no_key_401(client, db_engine):
    user, _ = _make_pro_user(db_engine)
    resp = client.get(f"/users/{user.id}")
    assert resp.status_code == 401
    assert "Missing API key" in resp.json()["detail"]


def test_patch_user_no_key_401(client, db_engine):
    user, _ = _make_pro_user(db_engine)
    resp = client.patch(f"/users/{user.id}", json={"name": "X"})
    assert resp.status_code == 401


def test_list_briefings_no_key_401(client, db_engine):
    user, _ = _make_pro_user(db_engine)
    resp = client.get(f"/users/{user.id}/briefings")
    assert resp.status_code == 401


def test_get_briefing_no_key_401(client, db_engine):
    user, _ = _make_pro_user(db_engine)
    resp = client.get(f"/users/{user.id}/briefings/1")
    assert resp.status_code == 401


def test_trigger_briefing_no_key_401(client, db_engine):
    user, _ = _make_pro_user(db_engine)
    resp = client.post(f"/users/{user.id}/briefings")
    assert resp.status_code == 401


def test_create_engagement_no_key_401(client):
    resp = client.post("/engagements", json={
        "user_id": 1, "cluster_id": 1, "action": "read",
    })
    assert resp.status_code == 401


# ── Invalid API key → 401 ───────────────────────────────────────────


def test_get_user_bad_key_401(client, db_engine):
    user, _ = _make_pro_user(db_engine)
    resp = client.get(
        f"/users/{user.id}",
        headers={"X-API-Key": "prism_bogus_key"},
    )
    assert resp.status_code == 401
    assert "Invalid API key" in resp.json()["detail"]


def test_patch_user_bad_key_401(client, db_engine):
    user, _ = _make_pro_user(db_engine)
    resp = client.patch(
        f"/users/{user.id}",
        json={"name": "X"},
        headers={"X-API-Key": "wrong"},
    )
    assert resp.status_code == 401


# ── Free user with key → 403 ────────────────────────────────────────


def test_free_user_key_403(client, db_engine):
    user, key = _make_free_user(db_engine)
    resp = client.get(
        f"/users/{user.id}",
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 403
    assert "Pro subscription" in resp.json()["detail"]


def test_free_user_patch_403(client, db_engine):
    user, key = _make_free_user(db_engine)
    resp = client.patch(
        f"/users/{user.id}",
        json={"name": "X"},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 403


def test_free_user_briefings_403(client, db_engine):
    user, key = _make_free_user(db_engine)
    resp = client.get(
        f"/users/{user.id}/briefings",
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 403


def test_free_user_engagements_403(client, db_engine):
    user, key = _make_free_user(db_engine)
    resp = client.post(
        "/engagements",
        json={"user_id": user.id, "cluster_id": 1, "action": "read"},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 403


# ── Valid pro API key → success ──────────────────────────────────────


def test_get_user_with_valid_key(client, db_engine):
    user, key = _make_pro_user(db_engine)
    resp = client.get(
        f"/users/{user.id}",
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    assert resp.json()["email"] == "pro@test.com"


def test_patch_user_with_valid_key(client, db_engine):
    user, key = _make_pro_user(db_engine)
    resp = client.patch(
        f"/users/{user.id}",
        json={"name": "Pro User"},
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Pro User"


def test_list_briefings_with_valid_key(client, db_engine):
    user, key = _make_pro_user(db_engine)
    resp = client.get(
        f"/users/{user.id}/briefings",
        headers={"X-API-Key": key},
    )
    assert resp.status_code == 200


# ── API key never leaked ─────────────────────────────────────────────


def test_user_response_does_not_contain_api_key(client, db_engine):
    user, key = _make_pro_user(db_engine)
    resp = client.get(
        f"/users/{user.id}",
        headers={"X-API-Key": key},
    )
    data = resp.json()
    assert "api_key" not in data
    assert key not in resp.text


def test_registration_does_not_return_api_key(client):
    resp = client.post("/users", json={
        "email": "nokey@test.com", "interests": "finance",
    })
    assert "api_key" not in resp.json()


# ── generate_api_key ─────────────────────────────────────────────────


def test_generate_api_key_prefix():
    raw_key, _ = generate_api_key()
    assert raw_key.startswith("prism_")


def test_generate_api_key_length():
    raw_key, _ = generate_api_key()
    # prism_ (6) + 43 chars of base64url = ~49 chars
    assert len(raw_key) > 30


def test_generate_api_key_unique():
    keys = {generate_api_key()[0] for _ in range(100)}
    assert len(keys) == 100


def test_generate_api_key_returns_tuple():
    result = generate_api_key()
    assert isinstance(result, tuple)
    assert len(result) == 2
    raw_key, key_hash = result
    assert raw_key.startswith("prism_")
    assert len(key_hash) == 64  # SHA-256 hex digest


def test_generate_api_key_hash_matches():
    raw_key, key_hash = generate_api_key()
    assert hash_api_key(raw_key) == key_hash


# ── Empty api_key field doesn't auth ─────────────────────────────────


def test_empty_api_key_header_401(client, db_engine):
    """Sending an empty X-API-Key header must be treated as missing."""
    user, _ = _make_pro_user(db_engine)
    resp = client.get(
        f"/users/{user.id}",
        headers={"X-API-Key": ""},
    )
    assert resp.status_code == 401


def test_user_with_no_api_key_field_cannot_auth(client, db_engine):
    """A user with api_key_hash='' must not match any lookup."""
    with Session(db_engine, expire_on_commit=False) as s:
        user = User(email="noapi@test.com", is_pro=True, api_key_hash="")
        s.add(user)
        s.commit()
    resp = client.get(
        f"/users/{user.id}",
        headers={"X-API-Key": ""},
    )
    assert resp.status_code == 401
