"""Tests for 02_02: Stripe Checkout Session endpoint."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from prism.api.app import create_app
from prism.api.routes import _get_session, require_api_key
from prism.db import init_db
from prism.models import User


# ── Fixtures ────────────────────────────────────────────────────────────

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
def free_user(db_session):
    user = User(email="free@test.com", is_pro=False)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def pro_user(db_session):
    user = User(email="pro@test.com", is_pro=True)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def returning_user(db_session):
    """A free user who previously had a Stripe customer (cancelled sub)."""
    user = User(
        email="returning@test.com",
        is_pro=False,
        stripe_customer_id="cus_existing_456",
    )
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
    """Set Stripe config so the endpoint doesn't return 503."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_test_fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    # Reset settings singleton so env vars are picked up
    import prism.config as cfg
    cfg._settings = None
    yield
    cfg._settings = None


@pytest.fixture()
def stripe_unconfigured(monkeypatch):
    """Ensure Stripe is NOT configured."""
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None
    yield
    cfg._settings = None


@pytest.fixture()
def mock_stripe():
    """Patch stripe SDK calls used by the checkout endpoint."""
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_123"

    mock_customer = MagicMock()
    mock_customer.id = "cus_new_789"

    with (
        patch("stripe.Customer.create", return_value=mock_customer) as cust_create,
        patch("stripe.checkout.Session.create", return_value=mock_session) as sess_create,
    ):
        m = MagicMock()
        m.Customer.create = cust_create
        m.checkout.Session.create = sess_create
        yield m


def _set_auth(user: User):
    _auth_state["user"] = user


# ── Auth & Access Control ────────────────────────────────────────────


def test_checkout_403_wrong_user(client, free_user, stripe_configured, mock_stripe):
    """User cannot create checkout for another user."""
    other = User(id=999, email="other@test.com", is_pro=True)
    _set_auth(other)
    resp = client.post(f"/users/{free_user.id}/checkout")
    assert resp.status_code == 403
    assert "access your own" in resp.json()["detail"].lower()


# ── Stripe Not Configured ───────────────────────────────────────────


def test_checkout_503_stripe_not_configured(client, free_user, stripe_unconfigured):
    """503 when Stripe keys are not set."""
    _set_auth(free_user)
    resp = client.post(f"/users/{free_user.id}/checkout")
    assert resp.status_code == 503
    assert "not configured" in resp.json()["detail"].lower()


# ── Already Pro ──────────────────────────────────────────────────────


def test_checkout_409_already_pro(client, pro_user, stripe_configured, mock_stripe):
    """Pro user gets 409."""
    _set_auth(pro_user)
    resp = client.post(f"/users/{pro_user.id}/checkout")
    assert resp.status_code == 409
    assert "already" in resp.json()["detail"].lower()


# ── Happy Path: New Customer ─────────────────────────────────────────


def test_checkout_creates_session(client, free_user, stripe_configured, mock_stripe):
    """Free user gets a checkout URL."""
    _set_auth(free_user)
    resp = client.post(f"/users/{free_user.id}/checkout")
    assert resp.status_code == 200
    data = resp.json()
    assert data["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_123"


def test_checkout_creates_customer_on_first_call(
    client, free_user, stripe_configured, mock_stripe, db_engine
):
    """First checkout creates a Stripe Customer and stores the ID."""
    _set_auth(free_user)
    client.post(f"/users/{free_user.id}/checkout")

    mock_stripe.Customer.create.assert_called_once()
    call_kwargs = mock_stripe.Customer.create.call_args[1]
    assert call_kwargs["email"] == "free@test.com"
    assert call_kwargs["metadata"]["prism_user_id"] == str(free_user.id)

    # Verify customer ID persisted to DB
    with Session(db_engine) as session:
        user = session.get(User, free_user.id)
        assert user.stripe_customer_id == "cus_new_789"


def test_checkout_session_params(client, free_user, stripe_configured, mock_stripe):
    """Verify the Stripe Checkout Session is created with correct params."""
    _set_auth(free_user)
    client.post(f"/users/{free_user.id}/checkout")

    mock_stripe.checkout.Session.create.assert_called_once()
    call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
    assert call_kwargs["mode"] == "subscription"
    assert call_kwargs["line_items"] == [{"price": "price_test_fake", "quantity": 1}]
    assert call_kwargs["customer"] == "cus_new_789"
    assert "upgraded=true" in call_kwargs["success_url"]
    assert "upgrade_cancelled=true" in call_kwargs["cancel_url"]
    assert call_kwargs["metadata"]["prism_user_id"] == str(free_user.id)
    assert call_kwargs["subscription_data"]["metadata"]["prism_user_id"] == str(free_user.id)


# ── Happy Path: Returning Customer ───────────────────────────────────


def test_checkout_reuses_existing_customer(
    client, returning_user, stripe_configured, mock_stripe
):
    """Returning customer skips Customer.create and reuses existing ID."""
    _set_auth(returning_user)
    resp = client.post(f"/users/{returning_user.id}/checkout")

    assert resp.status_code == 200
    mock_stripe.Customer.create.assert_not_called()
    call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
    assert call_kwargs["customer"] == "cus_existing_456"


# ── Stripe Error Handling ────────────────────────────────────────────


def test_checkout_502_on_stripe_error(client, free_user, stripe_configured, mock_stripe):
    """Stripe API error returns 502, not 500."""
    import stripe as stripe_mod

    mock_stripe.StripeError = stripe_mod.StripeError
    mock_stripe.Customer.create.side_effect = stripe_mod.StripeError("connection error")
    _set_auth(free_user)
    resp = client.post(f"/users/{free_user.id}/checkout")
    assert resp.status_code == 502
    assert "temporarily unavailable" in resp.json()["detail"].lower()


def test_checkout_502_on_session_create_error(
    client, returning_user, stripe_configured, mock_stripe
):
    """Stripe error during Session.create also returns 502."""
    import stripe as stripe_mod

    mock_stripe.StripeError = stripe_mod.StripeError
    mock_stripe.checkout.Session.create.side_effect = stripe_mod.StripeError("timeout")
    _set_auth(returning_user)
    resp = client.post(f"/users/{returning_user.id}/checkout")
    assert resp.status_code == 502


# ── Config: frontend_url ─────────────────────────────────────────────


def test_frontend_url_default(monkeypatch):
    """frontend_url defaults to localhost:3000."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None
    s = cfg.Settings()  # type: ignore[call-arg]
    assert s.frontend_url == "http://localhost:3000"
    cfg._settings = None


def test_frontend_url_from_env(monkeypatch):
    """frontend_url can be overridden via env."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("FRONTEND_URL", "https://prism.example.com")
    import prism.config as cfg
    cfg._settings = None
    s = cfg.Settings()  # type: ignore[call-arg]
    assert s.frontend_url == "https://prism.example.com"
    cfg._settings = None


def test_checkout_uses_frontend_url_in_redirects(
    client, free_user, mock_stripe, monkeypatch
):
    """success_url and cancel_url use the configured frontend_url."""
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_fake")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_test_fake")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("FRONTEND_URL", "https://prism.example.com")
    import prism.config as cfg
    cfg._settings = None

    _set_auth(free_user)
    client.post(f"/users/{free_user.id}/checkout")

    call_kwargs = mock_stripe.checkout.Session.create.call_args[1]
    assert call_kwargs["success_url"] == "https://prism.example.com/settings?upgraded=true"
    assert call_kwargs["cancel_url"] == "https://prism.example.com/settings?upgrade_cancelled=true"
    cfg._settings = None


# ── Response Schema ──────────────────────────────────────────────────


def test_checkout_response_schema(client, free_user, stripe_configured, mock_stripe):
    """Response body contains only checkout_url."""
    _set_auth(free_user)
    resp = client.post(f"/users/{free_user.id}/checkout")
    data = resp.json()
    assert set(data.keys()) == {"checkout_url"}
