"""Tests for resonance computation (T-RES.3 & T-RES.4)."""

import math
from datetime import UTC, datetime, timedelta

from prism.resonance import (
    MentionInput,
    ResonanceConfig,
    compute_momentum,
    compute_resonance,
)


NOW = datetime(2026, 5, 28, 12, 0, 0, tzinfo=UTC)


# --- T-RES.3: compute_resonance ---


def test_single_article_trust_1_age_0():
    """Single article, trust=1.0, no engagement, age=0 → resonance=1.0."""
    mentions = [MentionInput(source_id=1, trust_score=1.0, published_at=NOW)]
    result = compute_resonance(mentions, NOW)
    # breadth = log2(1+1) = 1.0, trust=1.0, engagement=1.0, decay=1.0
    assert result.resonance == 1.0
    assert result.mention_count == 1
    assert result.source_count == 1


def test_two_articles_same_source():
    """Two articles from same source → source_count=1, breadth=log2(2)=1.0."""
    mentions = [
        MentionInput(source_id=1, trust_score=0.8, published_at=NOW),
        MentionInput(source_id=1, trust_score=0.8, published_at=NOW),
    ]
    result = compute_resonance(mentions, NOW)
    assert result.source_count == 1
    assert result.breadth == math.log2(2)  # 1.0


def test_two_articles_different_sources():
    """Two articles from different sources → source_count=2, breadth=log2(3)."""
    mentions = [
        MentionInput(source_id=1, trust_score=1.0, published_at=NOW),
        MentionInput(source_id=2, trust_score=1.0, published_at=NOW),
    ]
    result = compute_resonance(mentions, NOW)
    assert result.source_count == 2
    assert result.breadth == pytest.approx(math.log2(3), rel=1e-9)


def test_decay_at_half_life():
    """Article aged exactly half_life_hours → decay = 0.5."""
    config = ResonanceConfig(half_life_hours=24.0)
    age = NOW - timedelta(hours=24)
    mentions = [MentionInput(source_id=1, trust_score=1.0, published_at=age)]
    result = compute_resonance(mentions, NOW, config)
    # breadth=1.0, trust=1.0, engagement=1.0, decay=0.5
    assert result.resonance == pytest.approx(0.5, rel=1e-9)


def test_zero_articles():
    """Zero articles → resonance=0.0, no division errors."""
    result = compute_resonance([], NOW)
    assert result.resonance == 0.0
    assert result.mention_count == 0
    assert result.source_count == 0
    assert result.authority_weighted_sum == 0.0
    assert result.breadth == 0.0


def test_engagement_zero_reactions():
    """0 reactions → engagement factor = 1.0 (no amplification)."""
    mentions = [
        MentionInput(source_id=1, trust_score=1.0, reactions=0, published_at=NOW),
    ]
    result = compute_resonance(mentions, NOW)
    assert result.resonance == 1.0  # breadth=1, trust=1, eng=1, decay=1


def test_engagement_at_median():
    """reactions = platform_median → engagement = 1 + log2(1+1) = 2.0."""
    config = ResonanceConfig(platform_median=50.0)
    mentions = [
        MentionInput(source_id=1, trust_score=1.0, reactions=50, published_at=NOW),
    ]
    result = compute_resonance(mentions, NOW, config)
    # breadth=1.0, trust=1.0, engagement=2.0, decay=1.0
    assert result.resonance == pytest.approx(2.0, rel=1e-9)


def test_authority_weighted_sum():
    """authority_weighted_sum = sum of trust scores."""
    mentions = [
        MentionInput(source_id=1, trust_score=0.9, published_at=NOW),
        MentionInput(source_id=2, trust_score=0.3, published_at=NOW),
    ]
    result = compute_resonance(mentions, NOW)
    assert result.authority_weighted_sum == pytest.approx(1.2, rel=1e-9)


def test_no_published_at_treated_as_age_zero():
    """Mention with no published_at → decay=1.0 (age 0)."""
    mentions = [MentionInput(source_id=1, trust_score=1.0, published_at=None)]
    result = compute_resonance(mentions, NOW)
    assert result.resonance == 1.0


# --- T-RES.4: compute_momentum ---


def test_momentum_rising():
    assert compute_momentum(10.0, 3.0) == 7.0


def test_momentum_fading():
    assert compute_momentum(2.0, 8.0) == -6.0


def test_momentum_stable():
    assert compute_momentum(5.0, 5.0) == 0.0


# --- pytest import ---
import pytest  # noqa: E402
