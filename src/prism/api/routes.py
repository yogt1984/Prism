"""Prism API routes — health, config, sources, stories, users, and engagements."""

import hashlib
import re as _re
import secrets
import time
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, EmailStr, model_validator

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.responses import Response, StreamingResponse
from fastapi.security import APIKeyHeader
from sqlmodel import Session, col, select

from prism.models import (
    Article,
    Briefing,
    BriefingFormat,
    Category,
    Engagement,
    KeywordMention,
    KeywordTrack,
    PerceptionSnapshot,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    TopicResonance,
    User,
)
from prism.onboarding import VALID_INTERESTS, RegistrationError, register_user

router = APIRouter()

_process_start_time = time.monotonic()


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


class ReadinessResponse(BaseModel):
    status: str
    db: str
    uptime_seconds: float
    last_cycles: dict[str, float | None]


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
    prompt_version: str
    quality_score: float
    resonance_score: float
    first_seen: datetime
    last_updated: datetime

    model_config = {"from_attributes": True}


class ResonanceOut(BaseModel):
    cluster_id: int
    resonance: float
    momentum: float
    peak_resonance: float
    mention_count: int
    source_count: int
    authority_weighted_sum: float
    breadth: float
    window_hours: int
    computed_at: datetime

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
    pro_since: datetime | None = None
    pro_until: datetime | None = None
    has_stripe_subscription: bool = False

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def derive_has_stripe(cls, data):  # type: ignore[no-untyped-def]
        if hasattr(data, "stripe_subscription_id"):
            data = dict(data) if not isinstance(data, dict) else data
            data["has_stripe_subscription"] = bool(data.get("stripe_subscription_id", ""))
        return data


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class BriefingOut(BaseModel):
    id: int
    user_id: int
    story_count: int
    prompt_version: str
    sent: bool
    sent_at: datetime | None
    created_at: datetime
    has_audio: bool = False
    audio_duration_sec: int = 0
    audio_size_bytes: int = 0

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def derive_has_audio(cls, data):  # type: ignore[no-untyped-def]
        if hasattr(data, "audio_path"):
            data = dict(data) if not isinstance(data, dict) else data
            data["has_audio"] = bool(data.get("audio_path", ""))
        return data


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


class KeywordCreate(BaseModel):
    keyword: str
    aliases: str = ""
    category: str = ""


class KeywordOut(BaseModel):
    id: int
    keyword: str
    aliases: str
    category: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class PerceptionOut(BaseModel):
    keyword_id: int
    perception: float
    salience: float
    valence: float
    momentum: float
    cluster_count: int
    source_count: int
    computed_at: datetime

    model_config = {"from_attributes": True}


# ── Endpoints ─────────────────────────────────────────────────────────


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe — always returns ok (backward compatible)."""
    return HealthResponse(status="ok")


@router.get("/health/live", response_model=HealthResponse)
def health_live() -> HealthResponse:
    """Liveness probe — always returns ok."""
    return HealthResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
def health_ready(session: Session = Depends(_get_session)) -> ReadinessResponse:
    """Readiness probe — checks DB connectivity and reports cycle status."""
    from prism.metrics import cycle_duration_seconds

    uptime = time.monotonic() - _process_start_time

    # Check DB connectivity
    try:
        session.exec(select(Source).limit(1))  # type: ignore[call-overload]
        db_status = "connected"
        status = "ok"
    except Exception as exc:
        db_status = f"unreachable: {exc}"
        status = "degraded"

    # Report last cycle timestamps from histogram
    hist_data = cycle_duration_seconds.snapshot()
    last_cycles: dict[str, float | None] = {
        "last_duration": hist_data.get("max") if hist_data.get("count", 0) > 0 else None,
        "total_cycles": hist_data.get("count"),
    }

    resp = ReadinessResponse(
        status=status,
        db=db_status,
        uptime_seconds=round(uptime, 2),
        last_cycles=last_cycles,
    )
    if status == "degraded":
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=503, content=resp.model_dump())  # type: ignore[return-value]
    return resp


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


_VALID_STORY_SORTS = {"first_seen", "resonance"}


@router.get("/stories", response_model=list[StoryOut])
def list_stories(
    status: Annotated[str | None, Query(description="Filter by status (raw/analyzed)")] = None,
    sort: Annotated[str, Query(description="Sort field: first_seen (default) or resonance")] = "first_seen",
    limit: Annotated[int, Query(ge=1, le=100, description="Max results")] = 20,
    offset: Annotated[int, Query(ge=0, description="Skip N results")] = 0,
    session: Session = Depends(_get_session),
) -> list[StoryOut]:
    """List story clusters with pagination."""
    if sort not in _VALID_STORY_SORTS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid sort '{sort}'. Valid: {', '.join(sorted(_VALID_STORY_SORTS))}",
        )
    stmt = select(StoryCluster)
    if status is not None:
        status_lower = status.lower()
        if status_lower not in {s.value for s in StoryStatus}:
            raise HTTPException(
                status_code=422,
                detail=f"Invalid status '{status}'. Valid: {', '.join(s.value for s in StoryStatus)}",
            )
        stmt = stmt.where(StoryCluster.status == status_lower)
    if sort == "resonance":
        stmt = stmt.order_by(col(StoryCluster.resonance_score).desc())
    else:
        stmt = stmt.order_by(col(StoryCluster.first_seen).desc())
    stmt = stmt.offset(offset).limit(limit)
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


@router.get("/stories/{story_id}/resonance", response_model=ResonanceOut)
def get_story_resonance(
    story_id: int,
    session: Session = Depends(_get_session),
) -> ResonanceOut:
    """Get the full resonance breakdown for a story."""
    cluster = session.get(StoryCluster, story_id)
    if cluster is None:
        raise HTTPException(status_code=404, detail="Story not found")

    tr = session.exec(
        select(TopicResonance).where(TopicResonance.cluster_id == story_id)
    ).first()
    if tr is None:
        raise HTTPException(status_code=404, detail="Resonance data not yet computed for this story")

    return ResonanceOut.model_validate(tr)


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


# ── Checkout ──────────────────────────────────────────────────────────


@router.post("/users/{user_id}/checkout", response_model=CheckoutResponse)
def create_checkout(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> CheckoutResponse:
    """Create a Stripe Checkout Session for Pro upgrade."""
    if auth_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: you can only access your own resources",
        )

    from prism.config import get_settings

    s = get_settings()
    if not s.stripe_secret_key or not s.stripe_price_id:
        raise HTTPException(
            status_code=503,
            detail="Payment processing is not configured",
        )

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_pro:
        raise HTTPException(
            status_code=409,
            detail="User is already a Pro subscriber",
        )

    import stripe

    stripe.api_key = s.stripe_secret_key

    try:
        if user.stripe_customer_id:
            customer_id = user.stripe_customer_id
        else:
            customer = stripe.Customer.create(
                email=user.email,
                metadata={"prism_user_id": str(user.id)},
            )
            customer_id = customer.id
            user.stripe_customer_id = customer_id
            session.add(user)
            session.commit()

        checkout_session = stripe.checkout.Session.create(
            customer=customer_id,
            mode="subscription",
            line_items=[{"price": s.stripe_price_id, "quantity": 1}],
            success_url=f"{s.frontend_url}/settings?upgraded=true",
            cancel_url=f"{s.frontend_url}/settings?upgrade_cancelled=true",
            metadata={"prism_user_id": str(user.id)},
            subscription_data={
                "metadata": {"prism_user_id": str(user.id)},
            },
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Payment service temporarily unavailable",
        ) from exc

    return CheckoutResponse(checkout_url=checkout_session.url)


# ── Portal ────────────────────────────────────────────────────────────


@router.post("/users/{user_id}/portal", response_model=PortalResponse)
def create_portal_session(
    user_id: int,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> PortalResponse:
    """Create a Stripe Customer Portal session for subscription management."""
    if auth_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: you can only access your own resources",
        )

    from prism.config import get_settings

    s = get_settings()
    if not s.stripe_secret_key:
        raise HTTPException(
            status_code=503,
            detail="Payment processing is not configured",
        )

    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.stripe_customer_id:
        raise HTTPException(
            status_code=409,
            detail="No subscription to manage",
        )

    import stripe

    stripe.api_key = s.stripe_secret_key

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=user.stripe_customer_id,
            return_url=f"{s.frontend_url}/settings",
        )
    except stripe.StripeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Billing portal temporarily unavailable",
        ) from exc

    return PortalResponse(portal_url=portal_session.url)


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


# ── Audio Streaming ───────────────────────────────────────────────────


def _serve_full(
    audio_file: Path,
    file_size: int,
    briefing_id: int,
) -> StreamingResponse:
    """Serve the complete MP3 file."""

    def file_iterator():  # type: ignore[no-untyped-def]
        with open(audio_file, "rb") as f:
            while chunk := f.read(65536):  # 64KB chunks
                yield chunk

    return StreamingResponse(
        content=file_iterator(),
        media_type="audio/mpeg",
        headers={
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="briefing-{briefing_id}.mp3"',
            "Cache-Control": "private, max-age=86400",
        },
    )


def _serve_range(
    audio_file: Path,
    file_size: int,
    range_header: str,
    briefing_id: int,
) -> Response:
    """Serve a byte range of the MP3 file (HTTP 206)."""
    match = _re.match(r"bytes=(\d+)-(\d*)", range_header)
    if not match:
        raise HTTPException(
            status_code=416, detail="Requested range not satisfiable"
        )

    start = int(match.group(1))
    end = int(match.group(2)) if match.group(2) else file_size - 1

    if start >= file_size or end >= file_size or start > end:
        raise HTTPException(
            status_code=416,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    content_length = end - start + 1

    def range_iterator():  # type: ignore[no-untyped-def]
        with open(audio_file, "rb") as f:
            f.seek(start)
            remaining = content_length
            while remaining > 0:
                chunk_size = min(65536, remaining)
                data = f.read(chunk_size)
                if not data:
                    break
                remaining -= len(data)
                yield data

    return StreamingResponse(
        content=range_iterator(),
        status_code=206,
        media_type="audio/mpeg",
        headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(content_length),
            "Accept-Ranges": "bytes",
            "Content-Disposition": f'inline; filename="briefing-{briefing_id}.mp3"',
            "Cache-Control": "private, max-age=86400",
        },
    )


@router.get("/users/{user_id}/briefings/{briefing_id}/audio")
def stream_audio(
    user_id: int,
    briefing_id: int,
    request: Request,
    auth_user: User = Depends(require_api_key),
    session: Session = Depends(_get_session),
) -> Response:
    """Stream the audio MP3 for a briefing."""
    if auth_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: you can only access your own resources",
        )

    briefing = session.get(Briefing, briefing_id)
    if briefing is None or briefing.user_id != user_id:
        raise HTTPException(status_code=404, detail="Briefing not found")

    if not briefing.audio_path:
        raise HTTPException(
            status_code=404, detail="Audio not available for this briefing"
        )

    from prism.config import get_settings

    audio_file = Path(get_settings().audio_storage_dir) / f"{briefing.id}.mp3"

    if not audio_file.exists():
        raise HTTPException(
            status_code=404, detail="Audio file missing from storage"
        )

    file_size = audio_file.stat().st_size

    range_header = request.headers.get("range")
    if range_header:
        return _serve_range(audio_file, file_size, range_header, briefing.id)
    return _serve_full(audio_file, file_size, briefing.id)


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


# ── Keywords & Perception ────────────────────────────────────────────


@router.get("/keywords", response_model=list[KeywordOut])
def list_keywords(
    active: Annotated[bool | None, Query(description="Filter by active status")] = None,
    session: Session = Depends(_get_session),
) -> list[KeywordOut]:
    """List tracked keywords."""
    stmt = select(KeywordTrack)
    if active is not None:
        stmt = stmt.where(KeywordTrack.is_active == active)
    stmt = stmt.order_by(col(KeywordTrack.keyword))
    rows = session.exec(stmt).all()
    return [KeywordOut.model_validate(r) for r in rows]


@router.post("/keywords", response_model=KeywordOut, status_code=201)
def create_keyword(
    body: KeywordCreate,
    session: Session = Depends(_get_session),
) -> KeywordOut:
    """Add a keyword to track."""
    existing = session.exec(
        select(KeywordTrack).where(KeywordTrack.keyword == body.keyword)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Keyword '{body.keyword}' already tracked")

    kw = KeywordTrack(keyword=body.keyword, aliases=body.aliases, category=body.category)
    session.add(kw)
    session.commit()
    session.refresh(kw)
    return KeywordOut.model_validate(kw)


@router.delete("/keywords/{keyword_id}", status_code=204)
def deactivate_keyword(
    keyword_id: int,
    session: Session = Depends(_get_session),
) -> None:
    """Deactivate a tracked keyword (preserves history)."""
    kw = session.get(KeywordTrack, keyword_id)
    if kw is None:
        raise HTTPException(status_code=404, detail="Keyword not found")
    kw.is_active = False
    session.add(kw)
    session.commit()


@router.get("/keywords/{keyword_id}/perception", response_model=PerceptionOut)
def get_keyword_perception(
    keyword_id: int,
    session: Session = Depends(_get_session),
) -> PerceptionOut:
    """Get the latest perception snapshot for a keyword."""
    kw = session.get(KeywordTrack, keyword_id)
    if kw is None:
        raise HTTPException(status_code=404, detail="Keyword not found")

    snap = session.exec(
        select(PerceptionSnapshot)
        .where(PerceptionSnapshot.keyword_id == keyword_id)
        .order_by(PerceptionSnapshot.computed_at.desc())  # type: ignore[union-attr]
    ).first()
    if snap is None:
        raise HTTPException(status_code=404, detail="No perception data yet for this keyword")

    return PerceptionOut.model_validate(snap)


@router.get("/keywords/{keyword_id}/perception/history", response_model=list[PerceptionOut])
def get_keyword_perception_history(
    keyword_id: int,
    limit: Annotated[int, Query(ge=1, le=500, description="Max snapshots")] = 50,
    session: Session = Depends(_get_session),
) -> list[PerceptionOut]:
    """Get perception history for a keyword (newest first)."""
    kw = session.get(KeywordTrack, keyword_id)
    if kw is None:
        raise HTTPException(status_code=404, detail="Keyword not found")

    rows = session.exec(
        select(PerceptionSnapshot)
        .where(PerceptionSnapshot.keyword_id == keyword_id)
        .order_by(PerceptionSnapshot.computed_at.desc())  # type: ignore[union-attr]
        .limit(limit)
    ).all()
    return [PerceptionOut.model_validate(r) for r in rows]
