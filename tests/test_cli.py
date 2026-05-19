"""T7.1: CLI scaffold tests.

Covers entrypoint, version, config show/check/env, --json global flag.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from prism.cli._fmt import mask_secret, set_json_mode
from prism.cli.app import app

runner = CliRunner()


@pytest.fixture(autouse=True)
def _reset_json_mode():
    """Ensure JSON mode is off between tests."""
    set_json_mode(False)
    yield
    set_json_mode(False)


# --- Entrypoint ---

def test_help_shows_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "version" in result.output
    assert "config" in result.output


def test_no_args_shows_help():
    result = runner.invoke(app, [])
    # Typer returns exit code 0 or 2 for no-args help depending on version.
    assert result.exit_code in (0, 2)
    assert "Usage" in result.output


# --- Version ---

def test_version_shows_info():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "Prism" in result.output
    assert "Python" in result.output


def test_version_shows_dependencies():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    for dep in ("anthropic", "httpx", "sqlmodel", "typer", "rich"):
        assert dep in result.output


def test_version_json():
    result = runner.invoke(app, ["--json", "version"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "prism" in data
    assert "python" in data
    assert "anthropic" in data


# --- Config show ---

def _mock_settings(**overrides):
    defaults = {
        "anthropic_api_key": "sk-ant-test-key-1234567890",
        "brave_api_key": "BSA-test-key",
        "resend_api_key": "",
        "database_url": "sqlite:///data/test.db",
        "briefing_from_email": "test@example.com",
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
    mock = MagicMock()
    for k, v in defaults.items():
        setattr(mock, k, v)
    mock.model_fields = defaults
    return mock


def test_config_show_masks_secrets():
    mock = _mock_settings()
    with patch("prism.cli.config_cmd._load_settings", return_value=(mock, None)):
        result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    # API keys should be masked
    assert "sk-ant-test-key-1234567890" not in result.output
    assert "****" in result.output
    # Non-secret values shown in full
    assert "sqlite:///data/test.db" in result.output


def test_config_show_json():
    mock = _mock_settings()
    with patch("prism.cli.config_cmd._load_settings", return_value=(mock, None)):
        result = runner.invoke(app, ["--json", "config", "show"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "anthropic_api_key" in data
    assert "sk-ant-test" not in data["anthropic_api_key"]
    assert data["database_url"] == "sqlite:///data/test.db"


def test_config_show_fails_gracefully():
    with patch("prism.cli.config_cmd._load_settings",
               return_value=(None, "missing anthropic_api_key")):
        result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 1


# --- Config check ---

def test_config_check_reports_missing_keys():
    mock = _mock_settings(anthropic_api_key="", brave_api_key="", resend_api_key="")
    with patch("prism.cli.config_cmd._load_settings", return_value=(mock, None)):
        result = runner.invoke(app, ["config", "check"])
    assert result.exit_code == 0
    assert "missing" in result.output


def test_config_check_json():
    mock = _mock_settings(anthropic_api_key="", brave_api_key="", resend_api_key="")
    with patch("prism.cli.config_cmd._load_settings", return_value=(mock, None)):
        result = runner.invoke(app, ["--json", "config", "check"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert isinstance(data, list)
    names = [r["name"] for r in data]
    assert "anthropic_api_key" in names


def test_config_check_warns_default_email():
    mock = _mock_settings(
        anthropic_api_key="",
        brave_api_key="",
        resend_api_key="",
        briefing_from_email="briefing@yourdomain.com",
    )
    with patch("prism.cli.config_cmd._load_settings", return_value=(mock, None)):
        result = runner.invoke(app, ["config", "check"])
    assert "default" in result.output


# --- Config env ---

def test_config_env_shows_template():
    result = runner.invoke(app, ["config", "env"])
    assert result.exit_code == 0
    assert "ANTHROPIC_API_KEY" in result.output
    assert "BRAVE_API_KEY" in result.output
    assert "DATABASE_URL" in result.output


def test_config_env_json():
    result = runner.invoke(app, ["--json", "config", "env"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "template" in data
    assert "ANTHROPIC_API_KEY" in data["template"]


# --- Formatting helpers ---

def test_mask_secret_long():
    assert mask_secret("sk-ant-abcdef1234567890") == "****7890"


def test_mask_secret_short():
    assert mask_secret("abc") == "****"


def test_mask_secret_empty():
    assert mask_secret("") == "(empty)"
