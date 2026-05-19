"""T5.1: Error recovery and retries tests.

Covers retry decorator with exponential backoff for external API calls.
"""

import logging
from unittest.mock import MagicMock, patch

import httpx
import pytest

from prism.retry import retry_on_transient

# --- Retry decorator tests ---

def test_retry_succeeds_first_try():
    mock_fn = MagicMock(return_value="ok")
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    assert decorated() == "ok"
    assert mock_fn.call_count == 1


def test_retry_succeeds_after_failure():
    mock_fn = MagicMock(side_effect=[httpx.TimeoutException("timeout"), "ok"])
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    assert decorated() == "ok"
    assert mock_fn.call_count == 2


def test_retry_exhausts_max_retries():
    mock_fn = MagicMock(side_effect=httpx.TimeoutException("timeout"))
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    with pytest.raises(httpx.TimeoutException):
        decorated()
    assert mock_fn.call_count == 3


def test_retry_logs_each_attempt(caplog):
    mock_fn = MagicMock(side_effect=[
        httpx.TimeoutException("timeout"),
        httpx.TimeoutException("timeout"),
        "ok",
    ])
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    with caplog.at_level(logging.WARNING):
        decorated()
    assert caplog.text.count("Retry") >= 2


def test_retry_does_not_catch_non_transient():
    """Non-transient errors (e.g. ValueError) should not be retried."""
    mock_fn = MagicMock(side_effect=ValueError("bad input"))
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    with pytest.raises(ValueError):
        decorated()
    assert mock_fn.call_count == 1


def test_retry_catches_rate_limit():
    """HTTP 429 responses should be retried."""
    resp_429 = httpx.Response(429, request=httpx.Request("GET", "https://x.com"))
    mock_fn = MagicMock(side_effect=[
        httpx.HTTPStatusError("rate limit", request=resp_429.request, response=resp_429),
        "ok",
    ])
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    assert decorated() == "ok"
    assert mock_fn.call_count == 2


def test_retry_catches_server_error():
    """HTTP 5xx responses should be retried."""
    resp_500 = httpx.Response(500, request=httpx.Request("GET", "https://x.com"))
    mock_fn = MagicMock(side_effect=[
        httpx.HTTPStatusError("server error", request=resp_500.request, response=resp_500),
        "ok",
    ])
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    assert decorated() == "ok"
    assert mock_fn.call_count == 2


def test_retry_does_not_catch_client_error():
    """HTTP 4xx (non-429) should NOT be retried."""
    resp_404 = httpx.Response(404, request=httpx.Request("GET", "https://x.com"))
    mock_fn = MagicMock(side_effect=httpx.HTTPStatusError(
        "not found", request=resp_404.request, response=resp_404,
    ))
    decorated = retry_on_transient(max_retries=3, base_delay=0.01)(mock_fn)
    with pytest.raises(httpx.HTTPStatusError):
        decorated()
    assert mock_fn.call_count == 1


def test_retry_exponential_delay():
    """Verify delays increase exponentially."""
    mock_fn = MagicMock(side_effect=[
        httpx.TimeoutException("t"),
        httpx.TimeoutException("t"),
        "ok",
    ])
    delays = []
    with patch("prism.retry.time.sleep", side_effect=lambda d: delays.append(d)):
        decorated = retry_on_transient(max_retries=3, base_delay=1.0)(mock_fn)
        decorated()
    assert len(delays) == 2
    assert delays[1] > delays[0]  # exponential growth


# --- Integration: agents use retry ---

def test_brave_search_retries_on_timeout():
    """DiscoveryAgent.search_brave retries on timeout."""
    from prism.agents.d_ai import DiscoveryAgent

    with patch.object(DiscoveryAgent, "__init__", lambda self: None):
        agent = DiscoveryAgent()
        agent.http = MagicMock()
        agent.http.get.side_effect = [
            httpx.TimeoutException("timeout"),
            MagicMock(
                status_code=200,
                json=MagicMock(return_value={"results": [{"title": "Test"}]}),
                raise_for_status=MagicMock(),
            ),
        ]
        result = agent.search_brave("test query")
        assert len(result) == 1
        assert agent.http.get.call_count == 2


def test_resend_retries_on_server_error():
    """WriterAgent.send_email retries on 5xx from Resend."""
    from prism.agents.w_ai import WriterAgent
    from prism.models import User

    with patch.object(WriterAgent, "__init__", lambda self: None):
        agent = WriterAgent()
        agent.client = MagicMock()
        user = User(email="test@test.com", interests="finance")

        with patch("prism.agents.w_ai.resend") as mock_resend:
            mock_resend.Emails.send.side_effect = [
                Exception("502 Bad Gateway"),
                {"id": "sent-123"},
            ]
            result = agent.send_email(user, "<p>content</p>")

        assert result is True
        assert mock_resend.Emails.send.call_count == 2
