"""T0.2: Configuration validation.

Tests that Settings loads from env, fails on missing required keys,
and has correct defaults.
"""

import pytest
from pydantic import ValidationError

from prism.config import Settings


def test_settings_loads_from_env(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test-123")
    monkeypatch.setenv("BRAVE_API_KEY", "brave-test-456")
    s = Settings()  # type: ignore[call-arg]
    assert s.anthropic_api_key == "sk-ant-test-123"
    assert s.brave_api_key == "brave-test-456"


def test_settings_missing_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None)  # type: ignore[call-arg]
    errors = exc_info.value.errors()
    assert any(e["loc"] == ("anthropic_api_key",) for e in errors)


def test_settings_defaults(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    s = Settings()  # type: ignore[call-arg]

    # Optional API keys default to empty
    assert s.brave_api_key == ""
    assert s.resend_api_key == ""

    # DB
    assert s.database_url == "sqlite:///data/newsgen.db"

    # D_AI
    assert s.discovery_interval_hours == 2
    assert s.max_stories_per_cycle == 50
    assert s.min_source_trust_score == 0.5

    # A_AI
    assert s.max_perspectives_per_story == 5
    assert s.max_input_tokens == 8000

    # P_AI
    assert s.default_briefing_stories == 10
    assert s.max_briefing_stories == 25

    # W_AI
    assert s.briefing_schedule_cron == "0 7 * * *"
    assert s.briefing_from_email == "briefing@yourdomain.com"

    # Resonance
    assert s.resonance_half_life_hours == 24
    assert s.resonance_window_hours == 72
    assert s.resonance_momentum_delta_hours == 6
    assert s.resonance_platform_median == 50


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("DISCOVERY_INTERVAL_HOURS", "6")
    monkeypatch.setenv("MAX_INPUT_TOKENS", "4000")
    s = Settings()  # type: ignore[call-arg]
    assert s.discovery_interval_hours == 6
    assert s.max_input_tokens == 4000


def test_resonance_settings_env_override(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    monkeypatch.setenv("RESONANCE_HALF_LIFE_HOURS", "48")
    monkeypatch.setenv("RESONANCE_WINDOW_HOURS", "120")
    monkeypatch.setenv("RESONANCE_MOMENTUM_DELTA_HOURS", "12")
    monkeypatch.setenv("RESONANCE_PLATFORM_MEDIAN", "100")
    s = Settings()  # type: ignore[call-arg]
    assert s.resonance_half_life_hours == 48
    assert s.resonance_window_hours == 120
    assert s.resonance_momentum_delta_hours == 12
    assert s.resonance_platform_median == 100
