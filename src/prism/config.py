from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    brave_api_key: str = ""
    resend_api_key: str = ""
    database_url: str = "sqlite:///data/newsgen.db"
    briefing_from_email: str = "briefing@yourdomain.com"

    # D_AI settings
    discovery_interval_hours: int = 2
    max_stories_per_cycle: int = 50
    min_source_trust_score: float = 0.5

    # A_AI settings
    max_perspectives_per_story: int = 5
    max_input_tokens: int = 8000

    # P_AI settings
    default_briefing_stories: int = 10
    max_briefing_stories: int = 25

    # W_AI settings
    briefing_schedule_cron: str = "0 7 * * *"  # 7 AM daily

    # Resonance
    resonance_half_life_hours: int = 24
    resonance_window_hours: int = 72
    resonance_momentum_delta_hours: int = 6
    resonance_platform_median: int = 50
    resonance_ranking_weight: float = 0.3

    # Perception tracking
    perception_half_life_hours: int = 24
    perception_window_hours: int = 72
    perception_scan_interval_minutes: int = 30

    # Monitoring
    ntfy_topic: str = ""  # ntfy.sh topic for push alerts (empty = disabled)

    # Stripe (required for payment, optional for dev without payments)
    stripe_secret_key: str = ""  # sk_test_... or sk_live_...
    stripe_publishable_key: str = ""  # pk_test_... or pk_live_...
    stripe_webhook_secret: str = ""  # whsec_...
    stripe_price_id: str = ""  # price_... ($7/mo recurring)
    grace_period_days: int = 7  # days before downgrade after payment failure
    frontend_url: str = "http://localhost:3000"  # base URL for redirect targets

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


_settings: Settings | None = None


def get_settings() -> Settings:
    """Lazy singleton — fails at first access, not at import time."""
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings


class _SettingsProxy:
    """Module-level proxy so `settings.x` keeps working without eager init."""

    def __getattr__(self, name: str):  # type: ignore[no-untyped-def]
        return getattr(get_settings(), name)


settings = _SettingsProxy()
