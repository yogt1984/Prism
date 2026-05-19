"""User onboarding — registration with validation."""

import logging
import re

from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.db import get_engine
from prism.models import User

logger = logging.getLogger(__name__)

VALID_INTERESTS = {
    "finance", "politics", "technology", "sports",
    "culture", "science", "health", "world",
}

# Simple email regex — covers the vast majority of valid addresses
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class RegistrationError(Exception):
    """Raised when user registration fails validation."""


def register_user(
    email: str,
    interests: str = "",
    briefing_depth: int = 10,
    engine: Engine | None = None,
) -> User:
    """Register a new user with validation.

    Args:
        email: User's email address.
        interests: Comma-separated interest categories.
        briefing_depth: Number of stories per briefing.
        engine: Optional SQLAlchemy engine (defaults to global).

    Returns:
        The created User object.

    Raises:
        RegistrationError: On invalid email, duplicate, or bad interests.
    """
    e = engine or get_engine()

    # Normalize
    email = email.strip().lower()

    # Validate email
    if not _EMAIL_RE.match(email):
        raise RegistrationError(f"Invalid email: {email}")

    # Validate interests
    if interests:
        for interest in interests.split(","):
            interest = interest.strip()
            if interest not in VALID_INTERESTS:
                raise RegistrationError(
                    f"Invalid interest: '{interest}'. "
                    f"Must be one of: {', '.join(sorted(VALID_INTERESTS))}"
                )

    # Check duplicate
    with Session(e) as session:
        existing = session.exec(
            select(User).where(User.email == email)
        ).first()
        if existing:
            raise RegistrationError(f"Email {email} is already registered")

        user = User(
            email=email,
            interests=interests,
            briefing_depth=briefing_depth,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        logger.info("Registered user: %s", email)
        return user
