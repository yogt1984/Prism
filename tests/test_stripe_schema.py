"""Tests for 02_01: Stripe schema, config, and UserOut changes."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key, UserOut
from prism.config import Settings
from prism.db import init_db
from prism.models import Source, StoryCluster, StripeEvent, User


# ── Fixtures ────────────────────────────────────────────────────────────

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


def _create_user(client, email="alice@example.com"):
    return client.post("/users", json={
        "email": email,
        "interests": "finance",
        "briefing_depth": 10,
    })


# ── User Model: Stripe field defaults ──────────────────────────────────


def test_user_stripe_fields_default_empty():
    user = User(email="test@example.com")
    assert user.stripe_customer_id == ""
    assert user.stripe_subscription_id == ""
    assert user.pro_since is None
    assert user.pro_until is None


def test_user_stripe_customer_id_set():
    user = User(email="t@t.com", stripe_customer_id="cus_abc123")
    assert user.stripe_customer_id == "cus_abc123"


def test_user_stripe_subscription_id_set():
    user = User(email="t@t.com", stripe_subscription_id="sub_xyz789")
    assert user.stripe_subscription_id == "sub_xyz789"


def test_user_pro_since_set():
    now = datetime.now(UTC)
    user = User(email="t@t.com", pro_since=now)
    assert user.pro_since == now


def test_user_pro_until_set():
    now = datetime.now(UTC)
    user = User(email="t@t.com", pro_until=now)
    assert user.pro_until == now


def test_user_stripe_fields_persist(tmp_path):
    """Stripe fields survive a DB roundtrip."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    now = datetime.now(UTC)
    with Session(engine) as session:
        user = User(
            email="pro@test.com",
            is_pro=True,
            stripe_customer_id="cus_test123",
            stripe_subscription_id="sub_test456",
            pro_since=now,
            pro_until=None,
        )
        session.add(user)
        session.commit()
        uid = user.id

    with Session(engine) as session:
        loaded = session.get(User, uid)
        assert loaded is not None
        assert loaded.stripe_customer_id == "cus_test123"
        assert loaded.stripe_subscription_id == "sub_test456"
        assert loaded.pro_since is not None
        assert loaded.pro_until is None
        assert loaded.is_pro is True


def test_existing_user_fields_preserved(tmp_path):
    """Creating a user without Stripe fields doesn't break existing fields."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        user = User(email="basic@test.com", interests="finance,politics")
        session.add(user)
        session.commit()
        uid = user.id

    with Session(engine) as session:
        loaded = session.get(User, uid)
        assert loaded is not None
        assert loaded.email == "basic@test.com"
        assert loaded.interests == "finance,politics"
        assert loaded.stripe_customer_id == ""
        assert loaded.is_pro is False


# ── StripeEvent Model ───────────────────────────────────────────────────


def test_stripe_event_creation():
    evt = StripeEvent(
        event_id="evt_test123",
        event_type="checkout.session.completed",
        user_id=1,
    )
    assert evt.event_id == "evt_test123"
    assert evt.event_type == "checkout.session.completed"
    assert evt.user_id == 1


def test_stripe_event_defaults():
    evt = StripeEvent(event_id="evt_abc")
    assert evt.event_type == ""
    assert evt.user_id is None
    assert evt.processed_at is not None


def test_stripe_event_persist(tmp_path):
    """StripeEvent survives a DB roundtrip."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        evt = StripeEvent(
            event_id="evt_roundtrip",
            event_type="invoice.paid",
            user_id=None,
        )
        session.add(evt)
        session.commit()
        eid = evt.id

    with Session(engine) as session:
        loaded = session.get(StripeEvent, eid)
        assert loaded is not None
        assert loaded.event_id == "evt_roundtrip"
        assert loaded.event_type == "invoice.paid"
        assert loaded.processed_at is not None


def test_stripe_event_unique_event_id(tmp_path):
    """Duplicate event_id must raise IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(StripeEvent(event_id="evt_dup"))
        session.commit()

    with pytest.raises(IntegrityError):
        with Session(engine) as session:
            session.add(StripeEvent(event_id="evt_dup"))
            session.commit()


def test_stripe_event_different_ids(tmp_path):
    """Different event IDs can coexist."""
    engine = create_engine(f"sqlite:///{tmp_path / 'test.db'}")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        session.add(StripeEvent(event_id="evt_1", event_type="checkout.session.completed"))
        session.add(StripeEvent(event_id="evt_2", event_type="invoice.paid"))
        session.commit()

    with Session(engine) as session:
        events = session.exec(select(StripeEvent)).all()
        assert len(events) == 2


# ── Config: Stripe settings ────────────────────────────────────────────


def test_stripe_config_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    s = Settings()  # type: ignore[call-arg]
    assert s.stripe_secret_key == ""
    assert s.stripe_publishable_key == ""
    assert s.stripe_webhook_secret == ""
    assert s.stripe_price_id == ""
    assert s.grace_period_days == 7


def test_stripe_config_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_abc")
    monkeypatch.setenv("STRIPE_PUBLISHABLE_KEY", "pk_test_xyz")
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_123")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_abc")
    monkeypatch.setenv("GRACE_PERIOD_DAYS", "14")
    s = Settings()  # type: ignore[call-arg]
    assert s.stripe_secret_key == "sk_test_abc"
    assert s.stripe_publishable_key == "pk_test_xyz"
    assert s.stripe_webhook_secret == "whsec_123"
    assert s.stripe_price_id == "price_abc"
    assert s.grace_period_days == 14


def test_stripe_config_no_startup_crash(monkeypatch):
    """App must start without Stripe vars set."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PUBLISHABLE_KEY", raising=False)
    s = Settings()  # type: ignore[call-arg]
    assert s.stripe_secret_key == ""


# ── UserOut Schema ──────────────────────────────────────────────────────


def test_userout_includes_new_fields():
    """UserOut must serialize pro_since, pro_until, has_stripe_subscription."""
    now = datetime.now(UTC)
    user = User(
        id=1,
        email="pro@test.com",
        is_pro=True,
        stripe_customer_id="cus_abc",
        stripe_subscription_id="sub_xyz",
        pro_since=now,
        pro_until=None,
    )
    out = UserOut.model_validate(user, from_attributes=True)
    assert out.pro_since == now
    assert out.pro_until is None
    assert out.has_stripe_subscription is True


def test_userout_has_stripe_subscription_false():
    """has_stripe_subscription is False when stripe_subscription_id is empty."""
    user = User(id=1, email="free@test.com", stripe_subscription_id="")
    out = UserOut.model_validate(user, from_attributes=True)
    assert out.has_stripe_subscription is False


def test_userout_does_not_expose_stripe_ids():
    """stripe_customer_id and stripe_subscription_id must not appear in output."""
    user = User(
        id=1,
        email="pro@test.com",
        stripe_customer_id="cus_secret",
        stripe_subscription_id="sub_secret",
    )
    out = UserOut.model_validate(user, from_attributes=True)
    data = out.model_dump()
    assert "stripe_customer_id" not in data
    assert "stripe_subscription_id" not in data


def test_userout_free_user_defaults():
    """Free user should have None for pro_since/pro_until, False for has_stripe."""
    user = User(id=1, email="free@test.com")
    out = UserOut.model_validate(user, from_attributes=True)
    assert out.pro_since is None
    assert out.pro_until is None
    assert out.has_stripe_subscription is False
    assert out.is_pro is False


# ── API: UserOut via GET /users/{id} ────────────────────────────────────


def test_api_user_response_has_new_fields(client):
    """GET /users/{id} must include pro_since, pro_until, has_stripe_subscription."""
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.get(f"/users/{user_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "pro_since" in data
    assert "pro_until" in data
    assert "has_stripe_subscription" in data
    assert data["has_stripe_subscription"] is False
    assert data["pro_since"] is None
    assert data["pro_until"] is None


def test_api_user_response_no_stripe_ids(client):
    """GET /users/{id} must NOT expose stripe_customer_id or stripe_subscription_id."""
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.get(f"/users/{user_id}")
    data = resp.json()
    assert "stripe_customer_id" not in data
    assert "stripe_subscription_id" not in data


def test_api_create_user_has_new_fields(client):
    """POST /users response must include the new fields."""
    resp = _create_user(client)
    data = resp.json()
    assert "pro_since" in data
    assert "pro_until" in data
    assert "has_stripe_subscription" in data


def test_api_patch_user_preserves_stripe_fields(client):
    """PATCH /users/{id} should not break the new fields in the response."""
    user_id = _create_user(client).json()["id"]
    _auth_state["user_id"] = user_id
    resp = client.patch(f"/users/{user_id}", json={"name": "Updated"})
    data = resp.json()
    assert data["name"] == "Updated"
    assert "has_stripe_subscription" in data
    assert data["has_stripe_subscription"] is False
