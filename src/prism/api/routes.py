"""Prism API routes — health and config endpoints."""

from pydantic import BaseModel

from fastapi import APIRouter

from prism.models import Category

router = APIRouter()


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
