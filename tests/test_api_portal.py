"""Tests for 02_04: Stripe Customer Portal endpoint."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key
from prism.db import init_db
from prism.models import User


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
def pro_user_with_customer(db_session):
    user = User(
        email="pro@test.com",
        is_pro=True,
        stripe_customer_id="cus_portal_123",
        stripe_subscription_id="sub_portal_456",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def free_user(db_session):
    user = User(email="free@test.com", is_pro=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def free_user_no_customer(db_session):
    """Free user who never subscribed (no stripe_customer_id)."""
    user = User(email="never@test.com", is_pro=False, stripe_customer_id="")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


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
def stripe_configured(monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None
    yield
    cfg._settings = None


@pytest.fixture()
def stripe_unconfigured(monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None
    yield
    cfg._settings = None


@pytest.fixture()
def mock_stripe():
    mock_portal = MagicMock()
    mock_portal.url = "https://billing.stripe.com/p/session/test_portal_123"

    with patch(
        "stripe.billing_portal.Session.create", return_value=mock_portal
    ) as portal_create:
        m = MagicMock()
        m.billing_portal.Session.create = portal_create
        yield m


def _set_auth(user: User):
    _auth_state["user"] = user


# ── Happy Path ───────────────────────────────────────────────────────


def test_portal_creates_session(
    client, pro_user_with_customer, stripe_configured, mock_stripe
):
    """Pro user with stripe_customer_id gets a portal URL."""
    _set_auth(pro_user_with_customer)
    resp = client.post(f"/users/{pro_user_with_customer.id}/portal")
    assert resp.status_code == 200
    assert "billing.stripe.com" in resp.json()["portal_url"]


def test_portal_response_schema(
    client, pro_user_with_customer, stripe_configured, mock_stripe
):
    """Response body contains only portal_url."""
    _set_auth(pro_user_with_customer)
    resp = client.post(f"/users/{pro_user_with_customer.id}/portal")
    assert set(resp.json().keys()) == {"portal_url"}


def test_portal_passes_correct_params(
    client, pro_user_with_customer, stripe_configured, mock_stripe, monkeypatch
):
    """Portal session is created with correct customer and return_url."""
    monkeypatch.setenv("FRONTEND_URL", "https://prism.example.com")
    import prism.config as cfg
    cfg._settings = None

    _set_auth(pro_user_with_customer)
    client.post(f"/users/{pro_user_with_customer.id}/portal")

    mock_stripe.billing_portal.Session.create.assert_called_once()
    call_kwargs = mock_stripe.billing_portal.Session.create.call_args[1]
    assert call_kwargs["customer"] == "cus_portal_123"
    assert call_kwargs["return_url"] == "https://prism.example.com/settings"

    cfg._settings = None


# ── Auth & Access Control ────────────────────────────────────────────


def test_portal_403_wrong_user(
    client, pro_user_with_customer, stripe_configured, mock_stripe
):
    """Cannot create portal for another user."""
    other = User(id=999, email="other@test.com", is_pro=True)
    _set_auth(other)
    resp = client.post(f"/users/{pro_user_with_customer.id}/portal")
    assert resp.status_code == 403


# ── No Stripe Customer ───────────────────────────────────────────────


def test_portal_409_no_customer_id(
    client, free_user_no_customer, stripe_configured, mock_stripe
):
    """User without stripe_customer_id gets 409."""
    _set_auth(free_user_no_customer)
    resp = client.post(f"/users/{free_user_no_customer.id}/portal")
    assert resp.status_code == 409
    assert "no subscription" in resp.json()["detail"].lower()


# ── Stripe Not Configured ───────────────────────────────────────────


def test_portal_503_stripe_not_configured(
    client, pro_user_with_customer, stripe_unconfigured
):
    """503 when Stripe keys are not set."""
    _set_auth(pro_user_with_customer)
    resp = client.post(f"/users/{pro_user_with_customer.id}/portal")
    assert resp.status_code == 503


# ── Stripe Error ─────────────────────────────────────────────────────


def test_portal_502_on_stripe_error(
    client, pro_user_with_customer, stripe_configured, mock_stripe
):
    """Stripe API error returns 502."""
    import stripe as stripe_mod

    mock_stripe.billing_portal.Session.create.side_effect = stripe_mod.StripeError(
        "service unavailable"
    )
    _set_auth(pro_user_with_customer)
    resp = client.post(f"/users/{pro_user_with_customer.id}/portal")
    assert resp.status_code == 502
    assert "temporarily unavailable" in resp.json()["detail"].lower()
