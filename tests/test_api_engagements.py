"""T10.6: POST /engagements endpoint tests."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key
from prism.db import init_db
from prism.models import StoryCluster, User

_FAKE_PRO = User(id=0, email="auth@test", is_pro=True)


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
    app.dependency_overrides[require_api_key] = lambda: _FAKE_PRO
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def _make_user(engine, email="test@example.com"):
    with Session(engine, expire_on_commit=False) as s:
        user = User(email=email, interests="finance")
        s.add(user)
        s.commit()
    return user


def _make_cluster(engine, headline="Test Event"):
    with Session(engine, expire_on_commit=False) as s:
        cluster = StoryCluster(headline=headline, article_count=1)
        s.add(cluster)
        s.commit()
    return cluster


def _post_engagement(client, user_id, cluster_id, action="read", read_time_sec=0):
    return client.post("/engagements", json={
        "user_id": user_id,
        "cluster_id": cluster_id,
        "action": action,
        "read_time_sec": read_time_sec,
    })


# ── Success cases ────────────────────────────────────────────────────


def test_create_engagement_success(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = _post_engagement(client, user.id, cluster.id, "read", 45)
    assert resp.status_code == 201
    data = resp.json()
    assert data["user_id"] == user.id
    assert data["cluster_id"] == cluster.id
    assert data["action"] == "read"
    assert data["read_time_sec"] == 45


def test_create_engagement_returns_id(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    data = _post_engagement(client, user.id, cluster.id).json()
    assert isinstance(data["id"], int)
    assert data["id"] > 0


def test_create_engagement_has_created_at(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    data = _post_engagement(client, user.id, cluster.id).json()
    assert "created_at" in data
    assert isinstance(data["created_at"], str)


def test_create_engagement_all_valid_actions(client, db_engine):
    """All four actions must be accepted."""
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    for action in ("open", "read", "save", "skip"):
        resp = _post_engagement(client, user.id, cluster.id, action)
        assert resp.status_code == 201, f"Action '{action}' rejected"
        assert resp.json()["action"] == action


def test_create_engagement_action_case_insensitive(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = _post_engagement(client, user.id, cluster.id, "READ")
    assert resp.status_code == 201
    assert resp.json()["action"] == "read"


def test_create_engagement_default_read_time(client, db_engine):
    """read_time_sec defaults to 0 when omitted."""
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = client.post("/engagements", json={
        "user_id": user.id,
        "cluster_id": cluster.id,
        "action": "open",
    })
    assert resp.status_code == 201
    assert resp.json()["read_time_sec"] == 0


def test_create_engagement_multiple_same_user_cluster(client, db_engine):
    """Multiple engagements for the same user+cluster are allowed (e.g. open then read)."""
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    r1 = _post_engagement(client, user.id, cluster.id, "open")
    r2 = _post_engagement(client, user.id, cluster.id, "read", 30)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] != r2.json()["id"]


# ── Validation failures ──────────────────────────────────────────────


def test_create_engagement_invalid_action(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = _post_engagement(client, user.id, cluster.id, "like")
    assert resp.status_code == 422
    assert "Invalid action" in resp.json()["detail"]


def test_create_engagement_invalid_action_lists_valid(client, db_engine):
    """Error message must list valid actions."""
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = _post_engagement(client, user.id, cluster.id, "bogus")
    detail = resp.json()["detail"]
    for valid in ("open", "read", "save", "skip"):
        assert valid in detail


def test_create_engagement_user_not_found(client, db_engine):
    cluster = _make_cluster(db_engine)
    resp = _post_engagement(client, 9999, cluster.id)
    assert resp.status_code == 422
    assert "User not found" in resp.json()["detail"]


def test_create_engagement_cluster_not_found(client, db_engine):
    user = _make_user(db_engine)
    resp = _post_engagement(client, user.id, 9999)
    assert resp.status_code == 422
    assert "Story not found" in resp.json()["detail"]


def test_create_engagement_both_missing(client):
    """Both user and cluster missing — user check should fail first."""
    resp = _post_engagement(client, 9999, 9999)
    assert resp.status_code == 422


def test_create_engagement_negative_read_time(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = _post_engagement(client, user.id, cluster.id, "read", -1)
    assert resp.status_code == 422
    assert "read_time_sec" in resp.json()["detail"]


def test_create_engagement_missing_required_fields(client):
    """Missing user_id or cluster_id should 422."""
    resp = client.post("/engagements", json={"action": "read"})
    assert resp.status_code == 422


def test_create_engagement_missing_action(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = client.post("/engagements", json={
        "user_id": user.id,
        "cluster_id": cluster.id,
    })
    assert resp.status_code == 422


# ── Response schema ──────────────────────────────────────────────────


def test_create_engagement_response_fields(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    data = _post_engagement(client, user.id, cluster.id, "save", 120).json()
    required = {"id", "user_id", "cluster_id", "action", "read_time_sec", "created_at"}
    assert required == set(data.keys())


def test_create_engagement_content_type(client, db_engine):
    user = _make_user(db_engine)
    cluster = _make_cluster(db_engine)
    resp = _post_engagement(client, user.id, cluster.id)
    assert "application/json" in resp.headers["content-type"]


def test_create_engagement_get_not_allowed(client):
    """GET /engagements should not exist (write-only endpoint)."""
    resp = client.get("/engagements")
    assert resp.status_code in (404, 405)
