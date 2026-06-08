"""Tests for 02_03: Stripe Webhook Handler."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from prism.api.app import create_app
from prism.api.stripe_webhook import _process_event
from prism.db import init_db
from prism.models import StripeEvent, User


# ── Helpers ──────────────────────────────────────────────────────────

_EVT_SEQ = 0


def make_event(event_type: str, data_object: dict, event_id: str | None = None) -> dict:
    """Build a Stripe-like event dict."""
    global _EVT_SEQ
    _EVT_SEQ += 1
    return {
        "id": event_id or f"evt_test_{_EVT_SEQ}",
        "type": event_type,
        "data": {"object": data_object},
    }


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_evt_seq():
    global _EVT_SEQ
    _EVT_SEQ = 0


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
    user = User(
        email="pro@test.com",
        is_pro=True,
        stripe_subscription_id="sub_active_123",
        pro_since=datetime(2025, 1, 1, tzinfo=UTC),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def grace_user(db_session):
    """Pro user with an active grace period."""
    user = User(
        email="grace@test.com",
        is_pro=True,
        stripe_subscription_id="sub_grace_456",
        pro_since=datetime(2025, 1, 1, tzinfo=UTC),
        pro_until=datetime.now(UTC) + timedelta(days=5),
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def _patch_engine(db_engine):
    """Route _process_event DB calls to test engine."""
    with patch("prism.api.stripe_webhook.get_engine", return_value=db_engine):
        yield


@pytest.fixture(autouse=True)
def _patch_alerts():
    """Suppress real alert calls."""
    with patch("prism.api.stripe_webhook.send_alert") as mock:
        yield mock


@pytest.fixture()
def mock_alerts(_patch_alerts):
    """Expose the mocked send_alert for assertions."""
    return _patch_alerts


@pytest.fixture()
def stripe_webhook_configured(monkeypatch):
    """Configure webhook secret for HTTP-level tests."""
    monkeypatch.setenv("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None
    yield
    cfg._settings = None


@pytest.fixture()
def client(db_engine):
    app = create_app()

    def _override():
        with Session(db_engine) as session:
            yield session

    # Only override session for the main routes, not webhook (it uses get_engine)
    from prism.api.routes import _get_session
    app.dependency_overrides[_get_session] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── checkout.session.completed ───────────────────────────────────────


def test_checkout_completed_activates_pro(db_engine, free_user):
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(free_user.id)},
        "subscription": "sub_test_123",
    })
    result = _process_event(event)
    assert result["status"] == "ok"

    with Session(db_engine) as session:
        user = session.get(User, free_user.id)
        assert user.is_pro is True
        assert user.stripe_subscription_id == "sub_test_123"
        assert user.pro_since is not None
        assert user.pro_until is None


def test_checkout_completed_clears_grace_period(db_engine, grace_user):
    """Re-subscribing clears any existing grace period."""
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(grace_user.id)},
        "subscription": "sub_new_789",
    })
    result = _process_event(event)
    assert result["status"] == "ok"

    with Session(db_engine) as session:
        user = session.get(User, grace_user.id)
        assert user.pro_until is None
        assert user.stripe_subscription_id == "sub_new_789"


def test_checkout_completed_preserves_pro_since(db_engine, pro_user):
    """Re-activation should not overwrite the original pro_since date."""
    original_pro_since = pro_user.pro_since
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(pro_user.id)},
        "subscription": "sub_renewed_999",
    })
    _process_event(event)

    with Session(db_engine) as session:
        user = session.get(User, pro_user.id)
        assert user.pro_since == original_pro_since


def test_checkout_completed_missing_metadata(db_engine, free_user):
    """Event without prism_user_id metadata is handled gracefully."""
    event = make_event("checkout.session.completed", {
        "metadata": {},
        "subscription": "sub_orphan",
    })
    result = _process_event(event)
    assert result["status"] == "ok"

    with Session(db_engine) as session:
        user = session.get(User, free_user.id)
        assert user.is_pro is False


def test_checkout_completed_unknown_user(db_engine):
    """Event for non-existent user is handled gracefully."""
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": "99999"},
        "subscription": "sub_ghost",
    })
    result = _process_event(event)
    assert result["status"] == "ok"


def test_checkout_completed_sends_alert(db_engine, free_user, mock_alerts):
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(free_user.id)},
        "subscription": "sub_alert",
    })
    _process_event(event)
    mock_alerts.assert_called_once()
    call_args = mock_alerts.call_args
    assert "free@test.com" in call_args[0][0]


# ── invoice.paid ─────────────────────────────────────────────────────


def test_invoice_paid_clears_grace(db_engine, grace_user):
    event = make_event("invoice.paid", {
        "subscription": grace_user.stripe_subscription_id,
    })
    result = _process_event(event)
    assert result["status"] == "ok"

    with Session(db_engine) as session:
        user = session.get(User, grace_user.id)
        assert user.pro_until is None
        assert user.is_pro is True


def test_invoice_paid_keeps_pro_active(db_engine, pro_user):
    event = make_event("invoice.paid", {
        "subscription": pro_user.stripe_subscription_id,
    })
    _process_event(event)

    with Session(db_engine) as session:
        user = session.get(User, pro_user.id)
        assert user.is_pro is True


def test_invoice_paid_unknown_subscription(db_engine):
    event = make_event("invoice.paid", {
        "subscription": "sub_nonexistent",
    })
    result = _process_event(event)
    assert result["status"] == "ok"


def test_invoice_paid_no_subscription_id(db_engine):
    """Event without subscription field is handled gracefully."""
    event = make_event("invoice.paid", {})
    result = _process_event(event)
    assert result["status"] == "ok"


# ── invoice.payment_failed ───────────────────────────────────────────


def test_payment_failed_sets_grace_period(db_engine, pro_user, monkeypatch):
    monkeypatch.setenv("GRACE_PERIOD_DAYS", "7")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None

    before = datetime.now(UTC)
    event = make_event("invoice.payment_failed", {
        "subscription": pro_user.stripe_subscription_id,
    })
    _process_event(event)

    with Session(db_engine) as session:
        user = session.get(User, pro_user.id)
        assert user.is_pro is True
        assert user.pro_until is not None
        expected = (before + timedelta(days=7)).replace(tzinfo=None)
        assert abs((user.pro_until - expected).total_seconds()) < 5

    cfg._settings = None


def test_payment_failed_sends_alert(db_engine, pro_user, mock_alerts, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None

    event = make_event("invoice.payment_failed", {
        "subscription": pro_user.stripe_subscription_id,
    })
    _process_event(event)

    mock_alerts.assert_called_once()
    call_args = mock_alerts.call_args
    assert "pro@test.com" in call_args[0][0]
    assert call_args[1]["level"].value == "warning"

    cfg._settings = None


def test_payment_failed_unknown_subscription(db_engine):
    event = make_event("invoice.payment_failed", {
        "subscription": "sub_nonexistent",
    })
    result = _process_event(event)
    assert result["status"] == "ok"


# ── customer.subscription.deleted ────────────────────────────────────


def test_subscription_deleted_sets_grace_and_clears_sub(db_engine, pro_user, monkeypatch):
    monkeypatch.setenv("GRACE_PERIOD_DAYS", "14")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None

    before = datetime.now(UTC)
    event = make_event("customer.subscription.deleted", {
        "id": pro_user.stripe_subscription_id,
    })
    _process_event(event)

    with Session(db_engine) as session:
        user = session.get(User, pro_user.id)
        assert user.stripe_subscription_id == ""
        assert user.pro_until is not None
        expected = (before + timedelta(days=14)).replace(tzinfo=None)
        assert abs((user.pro_until - expected).total_seconds()) < 5

    cfg._settings = None


def test_subscription_deleted_sends_alert(db_engine, pro_user, mock_alerts, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None

    event = make_event("customer.subscription.deleted", {
        "id": pro_user.stripe_subscription_id,
    })
    _process_event(event)

    mock_alerts.assert_called_once()
    call_args = mock_alerts.call_args
    assert "pro@test.com" in call_args[0][0]
    assert call_args[1]["level"].value == "warning"

    cfg._settings = None


def test_subscription_deleted_unknown_sub(db_engine):
    event = make_event("customer.subscription.deleted", {
        "id": "sub_nonexistent",
    })
    result = _process_event(event)
    assert result["status"] == "ok"


# ── Idempotency ──────────────────────────────────────────────────────


def test_duplicate_event_returns_duplicate(db_engine, free_user):
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(free_user.id)},
        "subscription": "sub_dup",
    }, event_id="evt_dedup_1")

    first = _process_event(event)
    assert first["status"] == "ok"

    second = _process_event(event)
    assert second["status"] == "duplicate"


def test_duplicate_event_no_db_changes(db_engine, free_user):
    """Second processing of same event must not alter user state."""
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(free_user.id)},
        "subscription": "sub_dup2",
    }, event_id="evt_dedup_2")

    _process_event(event)

    # Manually change user state to detect if second call modifies it
    with Session(db_engine) as session:
        user = session.get(User, free_user.id)
        user.stripe_subscription_id = "sub_changed"
        session.add(user)
        session.commit()

    _process_event(event)

    with Session(db_engine) as session:
        user = session.get(User, free_user.id)
        assert user.stripe_subscription_id == "sub_changed"


def test_stripe_event_recorded(db_engine, free_user):
    """Processed events are stored in StripeEvent table."""
    event = make_event("checkout.session.completed", {
        "metadata": {"prism_user_id": str(free_user.id)},
        "subscription": "sub_rec",
    }, event_id="evt_record_1")
    _process_event(event)

    with Session(db_engine) as session:
        stored = session.exec(
            select(StripeEvent).where(StripeEvent.event_id == "evt_record_1")
        ).first()
        assert stored is not None
        assert stored.event_type == "checkout.session.completed"
        assert stored.user_id == free_user.id


# ── Unhandled Event Types ────────────────────────────────────────────


def test_unknown_event_type_returns_skipped():
    event = make_event("charge.succeeded", {"amount": 700})
    result = _process_event(event)
    assert result["status"] == "skipped"


def test_unknown_event_not_stored(db_engine):
    """Skipped events should not be recorded in StripeEvent."""
    event = make_event("charge.succeeded", {"amount": 700}, event_id="evt_skip_1")
    _process_event(event)

    with Session(db_engine) as session:
        stored = session.exec(
            select(StripeEvent).where(StripeEvent.event_id == "evt_skip_1")
        ).first()
        assert stored is None


# ── HTTP-Level Tests (signature verification) ────────────────────────


def test_invalid_signature_returns_400(client, stripe_webhook_configured):
    resp = client.post(
        "/webhooks/stripe",
        content=b'{"id":"evt_1","type":"test"}',
        headers={"stripe-signature": "bad_sig"},
    )
    assert resp.status_code == 400
    assert "signature" in resp.json()["detail"].lower()


def test_missing_signature_returns_400(client, stripe_webhook_configured):
    resp = client.post(
        "/webhooks/stripe",
        content=b'{"id":"evt_1","type":"test"}',
    )
    assert resp.status_code == 400


def test_webhook_503_when_unconfigured(client, monkeypatch):
    """503 when webhook secret is not set."""
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None

    resp = client.post(
        "/webhooks/stripe",
        content=b'{}',
        headers={"stripe-signature": "test"},
    )
    assert resp.status_code == 503
    cfg._settings = None


# ── Rate Limit Exemption ─────────────────────────────────────────────


def test_webhook_exempt_from_rate_limit(client, stripe_webhook_configured):
    """Webhook endpoint should not be rate limited."""
    # Send many requests — should never get 429
    for _ in range(100):
        resp = client.post(
            "/webhooks/stripe",
            content=b'{}',
            headers={"stripe-signature": "test"},
        )
        # 400 is expected (bad sig), but NOT 429
        assert resp.status_code != 429
