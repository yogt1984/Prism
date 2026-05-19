"""T6.2: User onboarding tests.

Covers registration, email validation, duplicate rejection, default preferences.
"""

from pathlib import Path

import pytest
from sqlmodel import Session, select

from prism.db import init_db
from prism.models import BriefingFormat, User
from prism.onboarding import RegistrationError, register_user


@pytest.fixture()
def db_engine(tmp_path: Path):
    url = f"sqlite:///{tmp_path / 'test.db'}"
    engine = init_db(url)
    yield engine
    engine.dispose()


def test_register_user_creates_row(db_engine):
    user = register_user("alice@example.com", interests="finance,technology", engine=db_engine)
    assert user.id is not None

    with Session(db_engine) as s:
        stored = s.get(User, user.id)
        assert stored is not None
        assert stored.email == "alice@example.com"
        assert stored.interests == "finance,technology"


def test_register_duplicate_email(db_engine):
    register_user("bob@example.com", engine=db_engine)
    with pytest.raises(RegistrationError, match="already registered"):
        register_user("bob@example.com", engine=db_engine)

    # Verify only one row
    with Session(db_engine) as s:
        count = len(s.exec(select(User)).all())
        assert count == 1


def test_register_validates_email_format(db_engine):
    with pytest.raises(RegistrationError, match="Invalid email"):
        register_user("not-an-email", engine=db_engine)


def test_register_validates_email_missing_domain(db_engine):
    with pytest.raises(RegistrationError, match="Invalid email"):
        register_user("user@", engine=db_engine)


def test_register_validates_email_missing_local(db_engine):
    with pytest.raises(RegistrationError, match="Invalid email"):
        register_user("@domain.com", engine=db_engine)


def test_register_default_preferences(db_engine):
    user = register_user("carol@example.com", engine=db_engine)
    assert user.preferred_format == BriefingFormat.EMAIL
    assert user.briefing_depth == 10
    assert user.is_pro is False
    assert user.interests == ""


def test_register_with_custom_preferences(db_engine):
    user = register_user(
        "dave@example.com",
        interests="politics,sports",
        briefing_depth=5,
        engine=db_engine,
    )
    assert user.interests == "politics,sports"
    assert user.briefing_depth == 5


def test_register_validates_interests(db_engine):
    """Invalid interest categories should be rejected."""
    with pytest.raises(RegistrationError, match="Invalid interest"):
        register_user("eve@example.com", interests="finance,gossip", engine=db_engine)


def test_register_email_case_insensitive(db_engine):
    """Email lookup should be case-insensitive."""
    register_user("Frank@Example.COM", engine=db_engine)
    with pytest.raises(RegistrationError, match="already registered"):
        register_user("frank@example.com", engine=db_engine)


def test_register_strips_whitespace(db_engine):
    user = register_user("  grace@example.com  ", engine=db_engine)
    assert user.email == "grace@example.com"
