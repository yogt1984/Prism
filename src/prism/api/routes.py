"""Prism API routes — health, config, sources, stories, and users."""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, EmailStr

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, select

from prism.models import (
    Article,
    BriefingFormat,
    Category,
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


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe — always returns ok."""
    return HealthResponse(status="ok")


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
    session: Session = Depends(_get_session),
) -> UserOut:
    """Get a user profile by ID."""
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut.model_validate(user)


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    session: Session = Depends(_get_session),
) -> UserOut:
    """Update user profile fields."""
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
