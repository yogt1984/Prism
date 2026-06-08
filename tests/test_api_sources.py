"""Tests for 06_05: API source lifecycle endpoints."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key
from prism.db import init_db
from prism.models import Source, SourceStatus, User


# ── Fixtures ─────────────────────────────────────────────────────────

_auth_state: dict = {"user": None}


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


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
def auth_user(db_engine):
    """Create and return an authenticated pro user."""
    with Session(db_engine) as session:
        user = User(email="admin@test.com", is_pro=True)
        session.add(user)
        session.commit()
        session.refresh(user)
        _auth_state["user"] = User(id=user.id, email=user.email, is_pro=True)
        return user


# ── GET /sources/candidates ────────────────────────────────────────


def test_get_candidates(client, db_engine):
    with Session(db_engine) as session:
        session.add(Source(name="cand1", url="cand1.com", status=SourceStatus.CANDIDATE, sighting_count=5))
        session.add(Source(name="cand2", url="cand2.com", status=SourceStatus.CANDIDATE, sighting_count=2))
        session.add(Source(name="seed", url="seed.com", status=SourceStatus.SEED))
        session.commit()

    resp = client.get("/sources/candidates")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Ordered by sighting_count desc
    assert data[0]["url"] == "cand1.com"
    assert data[0]["sighting_count"] == 5
    assert data[0]["status"] == "candidate"


def test_get_candidates_empty(client):
    resp = client.get("/sources/candidates")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_candidates_with_limit(client, db_engine):
    with Session(db_engine) as session:
        for i in range(10):
            session.add(Source(name=f"c{i}", url=f"c{i}.com", status=SourceStatus.CANDIDATE))
        session.commit()

    resp = client.get("/sources/candidates?limit=3")
    assert resp.status_code == 200
    assert len(resp.json()) == 3


# ── GET /sources/probation ─────────────────────────────────────────


def test_get_probation(client, db_engine):
    from datetime import UTC, datetime
    with Session(db_engine) as session:
        session.add(Source(
            name="prob", url="prob.com", status=SourceStatus.PROBATION,
            articles_validated=8, articles_failed=2, trust_score=0.3,
            probation_start=datetime.now(UTC),
        ))
        session.commit()

    resp = client.get("/sources/probation")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["status"] == "probation"
    assert data[0]["articles_validated"] == 8
    assert data[0]["articles_failed"] == 2


# ── POST /sources/{id}/promote ─────────────────────────────────────


def test_promote_source(client, db_engine, auth_user):
    with Session(db_engine) as session:
        session.add(Source(name="Cand", url="cand.com", status=SourceStatus.CANDIDATE))
        session.commit()

    resp = client.post("/sources/1/promote")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "trusted"
    assert data["trust_score"] == 0.5
    assert data["active"] is True
    assert data["last_evaluated"] is not None


def test_promote_seed_returns_409(client, db_engine, auth_user):
    with Session(db_engine) as session:
        session.add(Source(name="AP", url="ap.com", status=SourceStatus.SEED))
        session.commit()

    resp = client.post("/sources/1/promote")
    assert resp.status_code == 409
    assert "seed" in resp.json()["detail"].lower()


def test_promote_not_found(client, auth_user):
    resp = client.post("/sources/999/promote")
    assert resp.status_code == 404


# ── POST /sources/{id}/reject ──────────────────────────────────────


def test_reject_source(client, db_engine, auth_user):
    with Session(db_engine) as session:
        session.add(Source(name="Bad", url="bad.com", status=SourceStatus.CANDIDATE))
        session.commit()

    resp = client.post("/sources/1/reject", json={"reason": "Unreliable content"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "rejected"
    assert data["rejection_reason"] == "Unreliable content"
    assert data["active"] is False
    assert data["trust_score"] == 0.0


def test_reject_seed_returns_409(client, db_engine, auth_user):
    with Session(db_engine) as session:
        session.add(Source(name="Reuters", url="reuters.com", status=SourceStatus.SEED))
        session.commit()

    resp = client.post("/sources/1/reject", json={"reason": "test"})
    assert resp.status_code == 409


def test_reject_not_found(client, auth_user):
    resp = client.post("/sources/999/reject", json={"reason": "gone"})
    assert resp.status_code == 404


# ── SourceOut schema ───────────────────────────────────────────────


def test_source_out_has_lifecycle_fields(client, db_engine):
    with Session(db_engine) as session:
        session.add(Source(
            name="test", url="test.com", status=SourceStatus.CANDIDATE,
            discovered_via="brave_search", sighting_count=3,
        ))
        session.commit()

    resp = client.get("/sources/candidates")
    assert resp.status_code == 200
    data = resp.json()[0]
    assert "status" in data
    assert "discovered_via" in data
    assert "sighting_count" in data
    assert "articles_validated" in data
    assert "articles_failed" in data
    assert "rejection_reason" in data


# ── Metrics ────────────────────────────────────────────────────────


def test_source_metrics_exist():
    from prism.metrics import (
        source_candidates_discovered_total,
        source_demoted_total,
        source_promoted_total,
        source_rejected_total,
    )
    assert source_candidates_discovered_total.name == "source_candidates_discovered_total"
    assert source_promoted_total.name == "source_promoted_total"
    assert source_rejected_total.name == "source_rejected_total"
    assert source_demoted_total.name == "source_demoted_total"


def test_source_metrics_in_snapshot():
    from prism.metrics import snapshot
    snap = snapshot()
    assert "source_candidates_discovered_total" in snap
    assert "source_promoted_total" in snap
    assert "source_rejected_total" in snap
    assert "source_demoted_total" in snap
