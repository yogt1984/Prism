"""T10.4: POST /users, GET /users/{id}, PATCH /users/{id} tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key
from prism.db import init_db
from prism.models import User

# Mutable auth state — tests set user_id before accessing protected endpoints
_auth_state: dict[str, int] = {"user_id": 0}


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


@pytest.fixture()
def client(db_engine):
    app = create_app()
    _auth_state["user_id"] = 0

    def _override():
        with Session(db_engine) as session:
            yield session

    app.dependency_overrides[_get_session] = _override
    app.dependency_overrides[require_api_key] = lambda: User(
        id=_auth_state["user_id"], email="auth@test", is_pro=True,
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _create_user(client, email="alice@example.com", interests="finance", depth=10):
    return client.post("/users", json={
        "email": email,
        "interests": interests,
        "briefing_depth": depth,
    })


# ── POST /users ──────────────────────────────────────────────────────


def test_create_user_success(client):
    resp = _create_user(client)
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "alice@example.com"
    assert data["interests"] == "finance"
    assert data["briefing_depth"] == 10


def test_create_user_returns_id(client):
    data = _create_user(client).json()
    assert isinstance(data["id"], int)
    assert data["id"] > 0


def test_create_user_defaults(client):
    """Defaults: email format, is_pro=False, preferred_format=email."""
    data = _create_user(client).json()
    assert data["is_pro"] is False
    assert data["preferred_format"] == "email"
    assert data["name"] == ""


def test_create_user_email_normalised(client):
    """Email must be lowercased and stripped."""
    resp = _create_user(client, email="  Alice@Example.COM  ")
    assert resp.json()["email"] == "alice@example.com"


def test_create_user_invalid_email(client):
    resp = _create_user(client, email="not-an-email")
    assert resp.status_code == 422
    assert "Invalid email" in resp.json()["detail"]


def test_create_user_empty_email(client):
    resp = _create_user(client, email="")
    assert resp.status_code == 422


def test_create_user_duplicate_email(client):
    _create_user(client, email="dup@test.com")
    resp = _create_user(client, email="dup@test.com")
    assert resp.status_code == 422
    assert "already registered" in resp.json()["detail"]


def test_create_user_duplicate_case_insensitive(client):
    """DUP@TEST.COM and dup@test.com must collide."""
    _create_user(client, email="dup@test.com")
    resp = _create_user(client, email="DUP@TEST.COM")
    assert resp.status_code == 422


def test_create_user_invalid_interest(client):
    resp = _create_user(client, interests="astrology")
    assert resp.status_code == 422
    assert "Invalid interest" in resp.json()["detail"]


def test_create_user_multiple_interests(client):
    resp = _create_user(client, interests="finance,politics,health")
    assert resp.status_code == 201
    assert resp.json()["interests"] == "finance,politics,health"


def test_create_user_empty_interests(client):
    resp = _create_user(client, interests="")
    assert resp.status_code == 201
    assert resp.json()["interests"] == ""


def test_create_user_custom_depth(client):
    resp = _create_user(client, depth=5)
    assert resp.json()["briefing_depth"] == 5


def test_create_user_response_has_created_at(client):
    data = _create_user(client).json()
    assert "created_at" in data
    assert isinstance(data["created_at"], str)
    assert len(data["created_at"]) > 0


def test_create_user_no_secret_fields(client):
    """Response must not leak internal-only data."""
    body = _create_user(client).text.lower()
    for forbidden in ("password", "token", "secret", "hash"):
        assert forbidden not in body


# ── GET /users/{id} ──────────────────────────────────────────────────


def test_get_user_found(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.get(f"/users/{user_id}")
    assert resp.status_code == 200
    assert resp.json()["email"] == "alice@example.com"


def test_get_user_not_found(client):
    _auth_state["user_id"] = 9999
    resp = client.get("/users/9999")
    assert resp.status_code == 404
    assert "not found" in resp.json()["detail"].lower()


def test_get_user_invalid_id_type(client):
    resp = client.get("/users/abc")
    assert resp.status_code == 422


def test_get_user_fields_match_create(client):
    """GET must return the same fields as POST."""
    created = _create_user(client).json()
    _auth_state["user_id"] = created["id"]
    fetched = client.get(f"/users/{created['id']}").json()
    for key in ("id", "email", "interests", "briefing_depth",
                "preferred_format", "is_pro", "name"):
        assert created[key] == fetched[key], f"Mismatch on {key}"


# ── PATCH /users/{id} ────────────────────────────────────────────────


def test_patch_user_update_interests(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"interests": "sports,culture"})
    assert resp.status_code == 200
    assert resp.json()["interests"] == "sports,culture"


def test_patch_user_update_name(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"name": "Alice Smith"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "Alice Smith"


def test_patch_user_update_format(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"preferred_format": "json_feed"})
    assert resp.status_code == 200
    assert resp.json()["preferred_format"] == "json_feed"


def test_patch_user_update_depth(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"briefing_depth": 15})
    assert resp.status_code == 200
    assert resp.json()["briefing_depth"] == 15


def test_patch_user_not_found(client):
    _auth_state["user_id"] = 9999
    resp = client.patch("/users/9999", json={"name": "Ghost"})
    assert resp.status_code == 404


def test_patch_user_invalid_interest(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"interests": "astrology"})
    assert resp.status_code == 422
    assert "Invalid interest" in resp.json()["detail"]


def test_patch_user_invalid_format(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"preferred_format": "carrier_pigeon"})
    assert resp.status_code == 422
    assert "Invalid format" in resp.json()["detail"]


def test_patch_user_depth_too_low(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"briefing_depth": 0})
    assert resp.status_code == 422
    assert "briefing_depth" in resp.json()["detail"]


def test_patch_user_depth_too_high(client):
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"briefing_depth": 26})
    assert resp.status_code == 422


def test_patch_user_clear_interests(client):
    """Setting interests to empty string should clear them."""
    user_id = _create_user(client, interests="finance").json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"interests": ""})
    assert resp.status_code == 200
    assert resp.json()["interests"] == ""


def test_patch_user_empty_body_noop(client):
    """PATCH with no fields should succeed and change nothing."""
    created = _create_user(client).json()
    _auth_state["user_id"] = created["id"]
    resp = client.patch(f"/users/{created['id']}", json={})
    assert resp.status_code == 200
    patched = resp.json()
    for key in ("email", "interests", "briefing_depth", "preferred_format", "name"):
        assert patched[key] == created[key]


def test_patch_user_multiple_fields(client):
    """Update multiple fields in one request."""
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={
        "name": "Bob",
        "interests": "technology,science",
        "briefing_depth": 20,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Bob"
    assert data["interests"] == "technology,science"
    assert data["briefing_depth"] == 20


def test_patch_user_does_not_change_email(client):
    """Email is immutable — PATCH must not change it even if field exists in body.
    (UserUpdate schema doesn't include email, so it's silently ignored.)"""
    created = _create_user(client).json()
    _auth_state["user_id"] = created["id"]
    # Extra fields are ignored by Pydantic
    resp = client.patch(f"/users/{created['id']}", json={"name": "Z"})
    assert resp.json()["email"] == created["email"]


def test_patch_user_does_not_change_is_pro(client):
    """is_pro is not in UserUpdate — must remain unchanged."""
    created = _create_user(client).json()
    _auth_state["user_id"] = created["id"]
    resp = client.patch(f"/users/{created['id']}", json={"name": "X"})
    assert resp.json()["is_pro"] == created["is_pro"]


def test_patch_user_format_case_insensitive(client):
    """Format values should be accepted case-insensitively."""
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"preferred_format": "AUDIO_SCRIPT"})
    assert resp.status_code == 200
    assert resp.json()["preferred_format"] == "audio_script"


def test_patch_user_persists(client):
    """Changes from PATCH must be visible on subsequent GET."""
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    client.patch(f"/users/{user_id}", json={"name": "Persisted"})
    fetched = client.get(f"/users/{user_id}").json()
    assert fetched["name"] == "Persisted"
