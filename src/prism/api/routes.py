"""Prism API routes — health, config, sources, stories, users, and engagements."""

import hashlib
import secrets
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import APIKeyHeader
from sqlmodel import Session, col, select

from prism.models import (
    Article,
    Briefing,
    BriefingFormat,
    Category,
    Engagement,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    User,
)
from prism.onboarding import VALID_INTERESTS, RegistrationError, register_user

router = APIRouter()


# ── Database dependency ───────────────────────────────────────────────


def _get_session():  # type: ignore[no-untyped-def]
    """Yield a DB session. Overridden in tests via app.dependency_overrides."""
    from prism.db import get_engine

    with Session(get_engine()) as session:
        yield session


# ── Auth dependency ──────────────────────────────────────────────────

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(raw_key: str) -> str:
    """Hash an API key with SHA-256 for storage."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


def require_api_key(
    api_key: str | None = Security(_api_key_header),
    session: Session = Depends(_get_session),
) -> User:
    """Validate X-API-Key header. Returns the authenticated pro user."""
    if not api_key:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hash_api_key(api_key)
    user = session.exec(
        select(User).where(User.api_key_hash == key_hash)
    ).first()

    if user is None:
        raise HTTPException(status_code=401, detail="Invalid API key")

    if not user.is_pro:
        raise HTTPException(status_code=403, detail="API access requires a Pro subscription")

    return user


def generate_api_key() -> tuple[str, str]:
    """Generate a cryptographically secure API key.

    Returns:
        Tuple of (raw_key, hashed_key).
    """
    raw = f"prism_{secrets.token_urlsafe(32)}"
    return raw, hash_api_key(raw)


# ── Response schemas ──────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str


class TierLimits(BaseModel):
    free_categories: int
    pro_categories: int
    free_max_stories: int
    pro_max_stories: int
    free_formats: list[str]
    pro_formats: list[str]


class ConfigResponse(BaseModel):
    discovery_interval_hours: int
    max_stories_per_cycle: int
    max_perspectives_per_story: int
    briefing_schedule_cron: str
    default_briefing_stories: int
    max_briefing_stories: int
    categories: list[str]
    tiers: TierLimits


class SourceOut(BaseModel):
    id: int
    name: str
    url: str
    rss_url: str
    trust_score: float
    bias_label: str
    categories: str
    active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class ArticleOut(BaseModel):
    id: int
    source_id: int
    title: str
    url: str
    snippet: str
    published_at: datetime | None
    fetched_at: datetime

    model_config = {"from_attributes": True}


class PerspectiveOut(BaseModel):
    id: int
    source_id: int
    summary: str
    sentiment: float
    bias_label: str
    key_claims: str

    model_config = {"from_attributes": True}


class StoryOut(BaseModel):
    id: int
    headline: str
    summary: str
    categories: str
    status: str
    article_count: int
    first_seen: datetime
    last_updated: datetime

    model_config = {"from_attributes": True}


class StoryDetailOut(StoryOut):
    articles: list[ArticleOut]
    perspectives: list[PerspectiveOut]


class UserCreate(BaseModel):
    email: str
    interests: str = ""
    briefing_depth: int = 10


class UserUpdate(BaseModel):
    interests: str | None = None
    preferred_format: str | None = None
    briefing_depth: int | None = None
    name: str | None = None


class UserOut(BaseModel):
    id: int
    email: str
    name: str
    interests: str
    preferred_format: str
    briefing_depth: int
    is_pro: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class BriefingOut(BaseModel):
    id: int
    user_id: int
    story_count: int
    sent: bool
    sent_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class BriefingDetailOut(BriefingOut):
    content_html: str
    content_text: str


_VALID_ACTIONS = {"open", "read", "save", "skip"}


class EngagementCreate(BaseModel):
    user_id: int
    cluster_id: int
    action: str
    read_time_sec: int = 0


class EngagementOut(BaseModel):
    id: int
    user_id: int
    cluster_id: int
    action: str
    read_time_sec: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe — always returns ok."""
    return HealthResponse(status="ok")


@router.get("/metrics")
def metrics() -> dict:
    """Return a JSON snapshot of all application metrics."""
    from prism.metrics import snapshot

    return snapshot()


@router.get("/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    """Public, non-secret runtime configuration."""
    from prism.config import get_settings

    s = get_settings()
    return ConfigResponse(
        discovery_interval_hours=s.discovery_interval_hours,
        max_stories_per_cycle=s.max_stories_per_cycle,
        max_perspectives_per_story=s.max_perspectives_per_story,
        briefing_schedule_cron=s.briefing_schedule_cron,
        default_briefing_stories=s.default_briefing_stories,
        max_briefing_stories=s.max_briefing_stories,
        categories=[c.value for c in Category],
        tiers=TierLimits(
            free_categories=1,
            pro_categories=len(Category),
            free_max_stories=s.default_briefing_stories,
            pro_max_stories=s.max_briefing_stories,
            free_formats=["email"],
            pro_formats=["email", "json_feed", "audio_script"],
        ),
    )


# ── Sources ───────────────────────────────────────────────────────────


@router.get("/sources", response_model=list[SourceOut])
def list_sources(
    active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    session: Session = Depends(_get_session),
) -> list[SourceOut]:
    """List news sources, optionally filtered by active status."""
    stmt = select(Source)
    if active is not None:
        stmt = stmt.where(Source.active == active)
    stmt = stmt.order_by(col(Source.trust_score).desc())
    rows = session.exec(stmt).all()
    return [SourceOut.model_validate(r) for r in rows]


# ── Stories ───────────────────────────────────────────────────────────


@router.get("/stories", response_model=list[StoryOut])
def list_stories(
    status: Annotated[str | None, Query(description="Filter by status (raw/analyzed)")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="Max results")] = 20,
    offset: Annotated[int, Query(ge=0, description="Skip N results")] = 0,
    session: Session = Depends(_get_session),
) -> list[StoryOut]:
    """List story clusters with pagination."""
    stmt = select(StoryCluster)
    if status is not None:
        status_lower = status.lower()
        if status_lower not in {s.value for s in StoryStatus}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{status}'. Valid: {', '.join(s.value for s in StoryStatus)}",
            )
        stmt = stmt.where(StoryCluster.status == status_lower)
    stmt = stmt.order_by(col(StoryCluster.first_seen).desc()).offset(offset).limit(limit)
    rows = session.exec(stmt).all()
    return [StoryOut.model_validate(r) for r in rows]


@router.get("/stories/{story_id}", response_model=StoryDetailOut)
def get_story(
    story_id: int,
    session: Session = Depends(_get_session),
) -> StoryDetailOut:
    """Get a single story with its articles and perspectives."""
    cluster = session.get(StoryCluster, story_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Story not found")

    articles = session.exec(
        select(Article).where(Article.cluster_id == story_id)
    ).all()
    perspectives = session.exec(
        select(Perspective).where(Perspective.cluster_id == story_id)
    ).all()

    data = StoryOut.model_validate(cluster).model_dump()
    data["articles"] = [ArticleOut.model_validate(a).model_dump() for a in articles]
    data["perspectives"] = [PerspectiveOut.model_validate(p).model_dump() for p in perspectives]
    return StoryDetailOut(**data)


# ── Users ─────────────────────────────────────────────────────────────

_VALID_FORMATS = {f.value for f in BriefingFormat}


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(
    body: UserCreate,
    session: Session = Depends(_get_session),
) -> UserOut:
    """Register a new user."""
    try:
        user = register_user(
            email=body.email,
            interests=body.interests,
            briefing_depth=body.briefing_depth,
            engine=session.get_bind(),
        )
    except RegistrationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return UserOut.model_validate(user)


@router.get("/users/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> UserOut:
    """Get a user profile by ID."""
    if auth_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: you can only access your own resources")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> UserOut:
    """Update user profile fields."""
    if auth_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: you can only access your own resources")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if body.interests is not None:
        if body.interests:
            for interest in body.interests.split(","):
                interest = interest.strip()
                if interest not in VALID_INTERESTS:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Invalid interest: '{interest}'. "
                        f"Must be one of: {', '.join(sorted(VALID_INTERESTS))}",
                    )
        user.interests = body.interests

    if body.preferred_format is not None:
        fmt = body.preferred_format.lower()
        if fmt not in _VALID_FORMATS:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid format: '{body.preferred_format}'. "
                f"Valid: {', '.join(sorted(_VALID_FORMATS))}",
            )
        user.preferred_format = BriefingFormat(fmt)

    if body.briefing_depth is not None:
        if body.briefing_depth < 1 or body.briefing_depth > 25:
            raise HTTPException(
                status_code=422,
                detail="briefing_depth must be between 1 and 25",
            )
        user.briefing_depth = body.briefing_depth

    if body.name is not None:
        user.name = body.name

    session.add(user)
    session.commit()
    session.refresh(user)
    return UserOut.model_validate(user)


# ── Briefings ─────────────────────────────────────────────────────────


@router.get("/users/{user_id}/briefings", response_model=list[BriefingOut])
def list_briefings(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    limit: Annotated[int, Query(ge=1, le=100, description="Max results")] = 20,
    offset: Annotated[int, Query(ge=0, description="Skip N results")] = 0,
    session: Session = Depends(_get_session),
) -> list[BriefingOut]:
    """List a user's briefings, newest first."""
    if auth_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: you can only access your own resources")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    stmt = (
        select(Briefing)
        .where(Briefing.user_id == user_id)
        .order_by(col(Briefing.created_at).desc())
        .offset(offset)
        .limit(limit)
    )
    rows = session.exec(stmt).all()
    return [BriefingOut.model_validate(r) for r in rows]


@router.get("/users/{user_id}/briefings/{briefing_id}", response_model=BriefingDetailOut)
def get_briefing(
    user_id: int,
    briefing_id: int,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> BriefingDetailOut:
    """Get a single briefing with full content."""
    if auth_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: you can only access your own resources")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    briefing = session.get(Briefing, briefing_id)
    if briefing is None or briefing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Briefing not found")

    return BriefingDetailOut.model_validate(briefing)


@router.post("/users/{user_id}/briefings", response_model=BriefingDetailOut, status_code=201)
def trigger_briefing(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> BriefingDetailOut:
    """Trigger on-demand briefing generation for a user."""
    if auth_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied: you can only access your own resources")
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    from prism.agents.p_ai import PersonalizationAgent
    from prism.agents.w_ai import WriterAgent

    engine = session.get_bind()
    p_ai = PersonalizationAgent()
    w_ai = WriterAgent()

    stories = p_ai.select_stories(user, engine=engine)
    briefing = w_ai.create_and_send(user, stories, engine=engine)

    if briefing is None:
        raise HTTPException(
            status_code=422,
            detail="No stories available for briefing generation",
        )

    return BriefingDetailOut.model_validate(briefing)


# ── Engagements ───────────────────────────────────────────────────────


@router.post("/engagements", response_model=EngagementOut, status_code=201)
def create_engagement(
    body: EngagementCreate,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> EngagementOut:
    """Record a user engagement event (open/read/save/skip)."""
    # Validate user exists
    user = session.get(User, body.user_id)
    if user is None:
        raise HTTPException(status_code=422, detail="User not found")

    # Validate cluster exists
    cluster = session.get(StoryCluster, body.cluster_id)
    if cluster is None:
        raise HTTPException(status_code=422, detail="Story not found")

    # Validate action
    action = body.action.lower()
    if action not in _VALID_ACTIONS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action '{body.action}'. "
            f"Valid: {', '.join(sorted(_VALID_ACTIONS))}",
        )

    # Validate read_time_sec
    if body.read_time_sec < 0:
        raise HTTPException(
            status_code=422,
            detail="read_time_sec must be >= 0",
        )

    engagement = Engagement(
        user_id=body.user_id,
        cluster_id=body.cluster_id,
        action=action,
        read_time_sec=body.read_time_sec,
    )
    session.add(engagement)
    session.commit()
    session.refresh(engagement)
    return EngagementOut.model_validate(engagement)
