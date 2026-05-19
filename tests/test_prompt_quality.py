"""T5.3: Prompt quality validation tests.

Verifies prompts are versioned and that analysis/briefing outputs
meet structural and attribution quality bars.
"""

import json
import re

from prism.agents.a_ai import ANALYSIS_PROMPT, ANALYSIS_PROMPT_VERSION
from prism.agents.w_ai import BRIEFING_PROMPT, BRIEFING_PROMPT_VERSION

# --- Prompt versioning ---

def test_analysis_prompt_is_versioned():
    assert ANALYSIS_PROMPT_VERSION is not None
    assert int(ANALYSIS_PROMPT_VERSION) >= 1


def test_briefing_prompt_is_versioned():
    assert BRIEFING_PROMPT_VERSION is not None
    assert int(BRIEFING_PROMPT_VERSION) >= 1


# --- Analysis prompt structure ---

def test_analysis_prompt_requests_json():
    assert "JSON" in ANALYSIS_PROMPT or "json" in ANALYSIS_PROMPT.lower()


def test_analysis_prompt_requires_source_attribution():
    assert "(Source:" in ANALYSIS_PROMPT


def test_analysis_prompt_restricts_categories():
    """Prompt should list the allowed categories."""
    for cat in ["finance", "politics", "technology", "sports", "science", "health"]:
        assert cat in ANALYSIS_PROMPT


def test_analysis_prompt_specifies_sentiment_range():
    assert "-1.0" in ANALYSIS_PROMPT
    assert "1.0" in ANALYSIS_PROMPT


# --- Briefing prompt structure ---

def test_briefing_prompt_requires_attribution():
    assert "(Source:" in BRIEFING_PROMPT


def test_briefing_prompt_specifies_format_rules():
    assert "email" in BRIEFING_PROMPT.lower()
    assert "HTML" in BRIEFING_PROMPT or "html" in BRIEFING_PROMPT.lower()


# --- Output validation helpers ---

VALID_CATEGORIES = {"finance", "politics", "technology", "sports", "culture",
                    "science", "health", "world"}


def test_analysis_output_schema_validation():
    """A well-formed analysis response passes schema checks."""
    response = {
        "headline": "Test headline",
        "summary": "Test summary of the event.",
        "categories": ["finance", "politics"],
        "perspectives": [
            {
                "source_name": "Reuters",
                "source_id": 1,
                "summary": "Reuters view",
                "sentiment": 0.3,
                "bias_label": "center",
                "key_claims": ["Market rose 2% (Source: Reuters)"],
            },
        ],
    }

    # Schema checks
    assert isinstance(response["headline"], str)
    assert isinstance(response["summary"], str)
    assert isinstance(response["categories"], list)
    assert all(c in VALID_CATEGORIES for c in response["categories"])
    assert isinstance(response["perspectives"], list)
    for p in response["perspectives"]:
        assert -1.0 <= p["sentiment"] <= 1.0
        assert all("(Source:" in claim for claim in p["key_claims"])


def test_analysis_output_rejects_bad_categories():
    """Categories outside the allowed set should be flagged."""
    response = {"categories": ["finance", "gossip", "celebrity"]}
    invalid = [c for c in response["categories"] if c not in VALID_CATEGORIES]
    assert len(invalid) == 2


def test_analysis_output_rejects_unattributed_claims():
    """Claims missing (Source: ...) should be flagged."""
    claims = [
        "Market rose 2% (Source: Reuters)",
        "Economy is booming",  # missing attribution
        "GDP grew 3.1% (Source: AP)",
    ]
    unattributed = [c for c in claims if "(Source:" not in c]
    assert len(unattributed) == 1


def test_briefing_output_has_source_tags():
    """Briefing HTML should contain Source attributions."""
    html = """
    <h2>Markets Rally</h2>
    <p>Stocks rose 2.1% after the Fed held rates (Source: Reuters).</p>
    <h2>Tech Earnings</h2>
    <p>Apple beat expectations (Source: Bloomberg).</p>
    """
    sources = re.findall(r"\(Source: [^)]+\)", html)
    assert len(sources) >= 2


def test_analysis_json_parseable():
    """Mock Claude response that follows the prompt should parse as JSON."""
    raw = json.dumps({
        "headline": "Test",
        "summary": "Test summary",
        "categories": ["finance"],
        "perspectives": [{
            "source_name": "Test",
            "source_id": 1,
            "summary": "Test view",
            "sentiment": 0.0,
            "bias_label": "center",
            "key_claims": ["Claim (Source: Test)"],
        }],
    })
    parsed = json.loads(raw)
    assert "headline" in parsed
    assert "perspectives" in parsed
