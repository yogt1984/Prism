"""T10.2: FastAPI health + config endpoint tests."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from prism.api.app import create_app
from prism.config import Settings
from prism.models import Category


def _fake_settings(**overrides) -> Settings:
    defaults = {
        "anthropic_api_key": "sk-test",
        "brave_api_key": "",
        "resend_api_key": "re_secret",
        "database_url": "sqlite:///test.db",
        "discovery_interval_hours": 2,
        "max_stories_per_cycle": 50,
        "min_source_trust_score": 0.5,
        "max_perspectives_per_story": 5,
        "max_input_tokens": 8000,
        "default_briefing_stories": 10,
        "max_briefing_stories": 25,
        "briefing_schedule_cron": "0 7 * * *",
        "ntfy_topic": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.fixture()
def client():
    app = create_app()
    with patch("prism.config.get_settings", return_value=_fake_settings()):
        with TestClient(app) as c:
            yield c


@pytest.fixture()
def raw_client():
    """Client without patched settings — for health which needs no config."""
    app = create_app()
    with TestClient(app) as c:
        yield c


# ── /health ───────────────────────────────────────────────────────────


def test_health_returns_200(raw_client):
    resp = raw_client.get("/health")
    assert resp.status_code == 200


def test_health_body(raw_client):
    data = raw_client.get("/health").json()
    assert data == {"status": "ok"}


def test_health_content_type(raw_client):
    resp = raw_client.get("/health")
    assert "application/json" in resp.headers["content-type"]


def test_health_no_sensitive_data(raw_client):
    """Health must never leak keys, DB URLs, or internal state."""
    body = raw_client.get("/health").text
    for secret_hint in ("api_key", "password", "secret", "sqlite", "token"):
        assert secret_hint not in body.lower()


def test_health_rejects_post(raw_client):
    resp = raw_client.post("/health")
    assert resp.status_code == 405


def test_health_idempotent(raw_client):
    """Multiple calls must return identical results."""
    r1 = raw_client.get("/health").json()
    r2 = raw_client.get("/health").json()
    assert r1 == r2


# ── /config ───────────────────────────────────────────────────────────


def test_config_returns_200(client):
    resp = client.get("/config")
    assert resp.status_code == 200


def test_config_has_required_keys(client):
    data = client.get("/config").json()
    required = {
        "discovery_interval_hours",
        "max_stories_per_cycle",
        "max_perspectives_per_story",
        "briefing_schedule_cron",
        "default_briefing_stories",
        "max_briefing_stories",
        "categories",
        "tiers",
    }
    assert required.issubset(set(data.keys()))


def test_config_categories_match_model(client):
    data = client.get("/config").json()
    expected = [c.value for c in Category]
    assert data["categories"] == expected


def test_config_categories_are_strings(client):
    cats = client.get("/config").json()["categories"]
    assert all(isinstance(c, str) for c in cats)
    assert len(cats) == 8


def test_config_no_secrets_leaked(client):
    """Config must never expose API keys, DB URL, or email credentials."""
    body = client.get("/config").text.lower()
    for secret in ("sk-test", "re_secret", "sqlite", "api_key",
                    "password", "anthropic", "resend", "brave"):
        assert secret not in body, f"Secret pattern '{secret}' found in /config"


def test_config_tiers_structure(client):
    tiers = client.get("/config").json()["tiers"]
    assert tiers["free_categories"] == 1
    assert tiers["pro_categories"] == len(Category)
    assert "email" in tiers["free_formats"]
    assert "json_feed" not in tiers["free_formats"]
    assert "json_feed" in tiers["pro_formats"]
    assert "audio_script" in tiers["pro_formats"]


def test_config_tier_story_limits(client):
    tiers = client.get("/config").json()["tiers"]
    assert tiers["free_max_stories"] == 10
    assert tiers["pro_max_stories"] == 25
    assert tiers["free_max_stories"] <= tiers["pro_max_stories"]


def test_config_values_match_settings(client):
    """Endpoint values must reflect the injected settings exactly."""
    data = client.get("/config").json()
    assert data["discovery_interval_hours"] == 2
    assert data["max_stories_per_cycle"] == 50
    assert data["max_perspectives_per_story"] == 5
    assert data["briefing_schedule_cron"] == "0 7 * * *"
    assert data["default_briefing_stories"] == 10
    assert data["max_briefing_stories"] == 25


def test_config_with_custom_settings():
    """Config must reflect overridden settings, not hardcoded defaults."""
    custom = _fake_settings(
        discovery_interval_hours=6,
        max_stories_per_cycle=100,
        briefing_schedule_cron="0 9 * * 1-5",
    )
    app = create_app()
    with patch("prism.config.get_settings", return_value=custom):
        with TestClient(app) as c:
            data = c.get("/config").json()
    assert data["discovery_interval_hours"] == 6
    assert data["max_stories_per_cycle"] == 100
    assert data["briefing_schedule_cron"] == "0 9 * * 1-5"


def test_config_rejects_post(client):
    resp = client.post("/config")
    assert resp.status_code == 405


def test_config_content_type(client):
    resp = client.get("/config")
    assert "application/json" in resp.headers["content-type"]


def test_config_response_is_valid_json(client):
    """Guard against malformed JSON or trailing garbage."""
    resp = client.get("/config")
    data = json.loads(resp.text)
    assert isinstance(data, dict)


# ── App factory ───────────────────────────────────────────────────────


def test_create_app_returns_fastapi():
    from fastapi import FastAPI
    app = create_app()
    assert isinstance(app, FastAPI)


def test_app_has_title():
    app = create_app()
    assert app.title == "Prism API"


def test_openapi_schema_loads(raw_client):
    """OpenAPI spec must generate without errors."""
    resp = raw_client.get("/openapi.json")
    assert resp.status_code == 200
    schema = resp.json()
    assert "/health" in schema["paths"]
    assert "/config" in schema["paths"]


def test_unknown_route_returns_404(raw_client):
    resp = raw_client.get("/nonexistent")
    assert resp.status_code == 404
