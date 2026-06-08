"""Tests for 02_04: Grace period expiry and subscription lifecycle."""

from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlmodel import Session, select

from prism.db import init_db
from prism.models import User
from prism.subscription import expire_grace_periods


# ── Fixtures ─────────────────────────────────────────────────────────


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


def _add_user(session, **kwargs):
    defaults = {"email": f"user{id(kwargs)}@test.com", "is_pro": False}
    defaults.update(kwargs)
    user = User(**defaults)
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture(autouse=True)
def _patch_alerts():
    with patch("prism.subscription.send_alert") as mock:
        yield mock


@pytest.fixture()
def mock_alerts(_patch_alerts):
    return _patch_alerts


# ── expire_grace_periods ─────────────────────────────────────────────


def test_expire_downgrades_past_grace(db_engine, db_session):
    """User with pro_until in the past gets downgraded."""
    user = _add_user(
        db_session,
        email="expired@test.com",
        is_pro=True,
        pro_until=datetime(2024, 1, 1, tzinfo=UTC),
        stripe_subscription_id="sub_stale",
    )
    count = expire_grace_periods(db_engine)
    assert count == 1

    with Session(db_engine) as s:
        loaded = s.get(User, user.id)
        assert loaded.is_pro is False
        assert loaded.stripe_subscription_id == ""


def test_expire_skips_future_grace(db_engine, db_session):
    """User with future pro_until stays Pro."""
    user = _add_user(
        db_session,
        email="future@test.com",
        is_pro=True,
        pro_until=datetime(2099, 1, 1, tzinfo=UTC),
    )
    count = expire_grace_periods(db_engine)
    assert count == 0

    with Session(db_engine) as s:
        loaded = s.get(User, user.id)
        assert loaded.is_pro is True


def test_expire_skips_free_users(db_engine, db_session):
    """Free users are not affected even if pro_until is somehow set."""
    _add_user(
        db_session,
        email="free@test.com",
        is_pro=False,
        pro_until=datetime(2024, 1, 1, tzinfo=UTC),
    )
    count = expire_grace_periods(db_engine)
    assert count == 0


def test_expire_skips_users_without_grace(db_engine, db_session):
    """Active Pro user without pro_until is not touched."""
    user = _add_user(
        db_session,
        email="active@test.com",
        is_pro=True,
        pro_until=None,
        stripe_subscription_id="sub_active",
    )
    count = expire_grace_periods(db_engine)
    assert count == 0

    with Session(db_engine) as s:
        loaded = s.get(User, user.id)
        assert loaded.is_pro is True
        assert loaded.stripe_subscription_id == "sub_active"


def test_expire_handles_multiple_users(db_engine, db_session):
    """Multiple expired users are all downgraded in one run."""
    for i in range(3):
        _add_user(
            db_session,
            email=f"expired{i}@test.com",
            is_pro=True,
            pro_until=datetime(2024, 1, 1, tzinfo=UTC),
        )
    # Also add one non-expired
    _add_user(
        db_session,
        email="safe@test.com",
        is_pro=True,
        pro_until=datetime(2099, 1, 1, tzinfo=UTC),
    )

    count = expire_grace_periods(db_engine)
    assert count == 3

    with Session(db_engine) as s:
        all_users = s.exec(select(User)).all()
        downgraded = [u for u in all_users if not u.is_pro]
        still_pro = [u for u in all_users if u.is_pro]
        assert len(downgraded) == 3
        assert len(still_pro) == 1


def test_expire_returns_zero_when_none(db_engine, db_session):
    """No users to expire returns 0."""
    _add_user(db_session, email="free@test.com", is_pro=False)
    count = expire_grace_periods(db_engine)
    assert count == 0


def test_expire_clears_subscription_id(db_engine, db_session):
    """Expired user's stripe_subscription_id is cleared."""
    user = _add_user(
        db_session,
        email="clear@test.com",
        is_pro=True,
        pro_until=datetime(2024, 1, 1, tzinfo=UTC),
        stripe_subscription_id="sub_clear_me",
    )
    expire_grace_periods(db_engine)

    with Session(db_engine) as s:
        loaded = s.get(User, user.id)
        assert loaded.stripe_subscription_id == ""


def test_expire_sends_alert(db_engine, db_session, mock_alerts):
    """Alert fires when users are downgraded."""
    _add_user(
        db_session,
        email="alert@test.com",
        is_pro=True,
        pro_until=datetime(2024, 1, 1, tzinfo=UTC),
    )
    expire_grace_periods(db_engine)

    mock_alerts.assert_called_once()
    msg = mock_alerts.call_args[0][0]
    assert "1 user(s)" in msg
    assert "downgraded" in msg.lower()


def test_expire_no_alert_when_none_expired(db_engine, db_session, mock_alerts):
    """No alert fires when nobody is downgraded."""
    _add_user(db_session, email="fine@test.com", is_pro=True, pro_until=None)
    expire_grace_periods(db_engine)
    mock_alerts.assert_not_called()


def test_expire_empty_db(db_engine):
    """Runs cleanly on empty database."""
    count = expire_grace_periods(db_engine)
    assert count == 0


# ── Scheduler integration ────────────────────────────────────────────


def test_scheduler_has_grace_period_job(monkeypatch):
    """build_scheduler includes the grace_period_check job."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    import prism.config as cfg
    cfg._settings = None

    from prism.main import build_scheduler
    scheduler = build_scheduler()
    job_ids = [j.id for j in scheduler.get_jobs()]
    assert "grace_period_check" in job_ids
    cfg._settings = None


# ── Lifecycle scenarios ──────────────────────────────────────────────


def test_lifecycle_payment_during_grace_restores(db_engine, db_session):
    """Simulates: grace set → invoice.paid → grace cleared → expiry skips."""
    user = _add_user(
        db_session,
        email="recover@test.com",
        is_pro=True,
        stripe_subscription_id="sub_recover",
        pro_until=datetime.now(UTC) + timedelta(days=5),
    )

    # Simulate invoice.paid clearing grace
    with Session(db_engine) as s:
        u = s.get(User, user.id)
        u.pro_until = None
        u.is_pro = True
        s.add(u)
        s.commit()

    # Expiry job should skip this user
    count = expire_grace_periods(db_engine)
    assert count == 0

    with Session(db_engine) as s:
        loaded = s.get(User, user.id)
        assert loaded.is_pro is True


def test_lifecycle_multiple_failures_reset_grace(db_engine, db_session):
    """Multiple payment failures reset grace to latest window."""
    user = _add_user(
        db_session,
        email="multi@test.com",
        is_pro=True,
        stripe_subscription_id="sub_multi",
        pro_until=datetime.now(UTC) + timedelta(days=3),  # first failure
    )

    # Second failure resets to a fresh 7-day window
    new_grace = datetime.now(UTC) + timedelta(days=7)
    with Session(db_engine) as s:
        u = s.get(User, user.id)
        u.pro_until = new_grace
        s.add(u)
        s.commit()

    # Expiry job should NOT downgrade — grace is in the future
    count = expire_grace_periods(db_engine)
    assert count == 0

    with Session(db_engine) as s:
        loaded = s.get(User, user.id)
        assert loaded.is_pro is True
