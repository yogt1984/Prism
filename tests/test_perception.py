"""Tests for perception computation — pure function tests."""

import math
from datetime import UTC, datetime, timedelta

import pytest

from prism.perception import (
    ClusterInput,
    PerceptionConfig,
    PerspectiveInput,
    compute_perception,
    compute_perception_momentum,
    scan_cluster_for_keyword,
    scan_text_for_keywords,
)


NOW = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)


# --- scan_text_for_keywords ---


def test_scan_exact_match():
    assert scan_text_for_keywords("tariff hike announced", ["tariff"]) == 1


def test_scan_case_insensitive():
    assert scan_text_for_keywords("Tariff Hike Announced", ["tariff"]) == 1


def test_scan_multiple_matches():
    assert scan_text_for_keywords("tariff on tariff off", ["tariff"]) == 2


def test_scan_multiple_terms():
    assert scan_text_for_keywords("tariff and trade barriers", ["tariff", "trade barriers"]) == 2


def test_scan_word_boundary():
    """Should not match partial words."""
    assert scan_text_for_keywords("artificial intelligence", ["art"]) == 0


def test_scan_empty_text():
    assert scan_text_for_keywords("", ["tariff"]) == 0


def test_scan_empty_terms():
    assert scan_text_for_keywords("some text", []) == 0


# --- scan_cluster_for_keyword ---


def test_cluster_scan_headline_hit():
    result = scan_cluster_for_keyword(
        headline="New tariff policy announced",
        article_titles=["Tariff details emerge"],
        source_ids=[1],
        trust_map={1: 0.8},
        keyword="tariff",
        aliases=[],
        cluster_id=10,
    )
    assert result is not None
    assert result.headline_hit is True
    assert result.mention_count >= 2  # headline + article


def test_cluster_scan_no_match():
    result = scan_cluster_for_keyword(
        headline="Weather forecast for tomorrow",
        article_titles=["Sunny skies expected"],
        source_ids=[1],
        trust_map={1: 0.8},
        keyword="tariff",
        aliases=[],
        cluster_id=10,
    )
    assert result is None


def test_cluster_scan_alias_match():
    result = scan_cluster_for_keyword(
        headline="Trade barriers increase",
        article_titles=["New duties on imports"],
        source_ids=[1],
        trust_map={1: 0.9},
        keyword="tariff",
        aliases=["trade barriers", "duties"],
        cluster_id=10,
    )
    assert result is not None
    assert result.mention_count >= 2


def test_cluster_scan_weighted_score():
    result = scan_cluster_for_keyword(
        headline="Other news",
        article_titles=["Tariff details", "Tariff impact"],
        source_ids=[1, 2],
        trust_map={1: 0.8, 2: 0.6},
        keyword="tariff",
        aliases=[],
        cluster_id=10,
    )
    assert result is not None
    assert result.source_count == 2
    assert result.weighted_score == pytest.approx(0.8 + 0.6, rel=1e-9)


# --- compute_perception ---


def test_empty_clusters():
    result = compute_perception([], NOW)
    assert result.perception == 0.0
    assert result.salience == 0.0
    assert result.valence == 0.0
    assert result.cluster_count == 0
    assert result.source_count == 0


def test_single_positive_cluster():
    """One cluster, one positive perspective, fresh."""
    clusters = [
        ClusterInput(
            cluster_id=1,
            source_count=1,
            first_seen=NOW,
            perspectives=[
                PerspectiveInput(source_id=1, trust_score=1.0, sentiment=1.0),
            ],
        ),
    ]
    result = compute_perception(clusters, NOW)
    # salience = log2(1+1) * decay(0) = 1.0 * 1.0 = 1.0
    # valence = (1.0 * 1.0 * 1.0) / (1.0 * 1.0) = 1.0
    # perception = 1.0 * 1.0 = 1.0
    assert result.perception == pytest.approx(1.0)
    assert result.salience == pytest.approx(1.0)
    assert result.valence == pytest.approx(1.0)


def test_single_negative_cluster():
    """Negative sentiment → negative perception."""
    clusters = [
        ClusterInput(
            cluster_id=1,
            source_count=1,
            first_seen=NOW,
            perspectives=[
                PerspectiveInput(source_id=1, trust_score=1.0, sentiment=-0.8),
            ],
        ),
    ]
    result = compute_perception(clusters, NOW)
    assert result.perception < 0
    assert result.valence == pytest.approx(-0.8)


def test_balanced_coverage_near_zero_valence():
    """Equal positive and negative perspectives → valence near zero."""
    clusters = [
        ClusterInput(
            cluster_id=1,
            source_count=2,
            first_seen=NOW,
            perspectives=[
                PerspectiveInput(source_id=1, trust_score=0.8, sentiment=0.7),
                PerspectiveInput(source_id=2, trust_score=0.8, sentiment=-0.7),
            ],
        ),
    ]
    result = compute_perception(clusters, NOW)
    assert abs(result.valence) < 0.01
    assert abs(result.perception) < 0.1


def test_decay_reduces_salience():
    """Older cluster → lower salience."""
    fresh = [
        ClusterInput(
            cluster_id=1, source_count=1, first_seen=NOW,
            perspectives=[PerspectiveInput(source_id=1, trust_score=1.0, sentiment=0.5)],
        ),
    ]
    old = [
        ClusterInput(
            cluster_id=2, source_count=1, first_seen=NOW - timedelta(hours=48),
            perspectives=[PerspectiveInput(source_id=1, trust_score=1.0, sentiment=0.5)],
        ),
    ]
    r_fresh = compute_perception(fresh, NOW)
    r_old = compute_perception(old, NOW)
    assert r_fresh.salience > r_old.salience


def test_breadth_amplifies():
    """More sources → higher salience via breadth factor."""
    narrow = [
        ClusterInput(
            cluster_id=1, source_count=1, first_seen=NOW,
            perspectives=[PerspectiveInput(source_id=1, trust_score=1.0, sentiment=0.5)],
        ),
    ]
    broad = [
        ClusterInput(
            cluster_id=2, source_count=8, first_seen=NOW,
            perspectives=[PerspectiveInput(source_id=1, trust_score=1.0, sentiment=0.5)],
        ),
    ]
    r_narrow = compute_perception(narrow, NOW)
    r_broad = compute_perception(broad, NOW)
    assert r_broad.salience > r_narrow.salience


def test_trust_weights_sentiment():
    """High-trust negative should outweigh low-trust positive."""
    clusters = [
        ClusterInput(
            cluster_id=1,
            source_count=2,
            first_seen=NOW,
            perspectives=[
                PerspectiveInput(source_id=1, trust_score=0.9, sentiment=-0.5),
                PerspectiveInput(source_id=2, trust_score=0.1, sentiment=0.5),
            ],
        ),
    ]
    result = compute_perception(clusters, NOW)
    assert result.valence < 0  # high-trust negative wins


def test_perception_at_half_life():
    """At exactly half_life, decay = 0.5."""
    config = PerceptionConfig(half_life_hours=24.0)
    clusters = [
        ClusterInput(
            cluster_id=1, source_count=1,
            first_seen=NOW - timedelta(hours=24),
            perspectives=[PerspectiveInput(source_id=1, trust_score=1.0, sentiment=1.0)],
        ),
    ]
    result = compute_perception(clusters, NOW, config)
    assert result.salience == pytest.approx(0.5, rel=1e-9)


def test_multi_cluster_aggregation():
    """Perception aggregates across multiple clusters."""
    clusters = [
        ClusterInput(
            cluster_id=1, source_count=1, first_seen=NOW,
            perspectives=[PerspectiveInput(source_id=1, trust_score=1.0, sentiment=0.8)],
        ),
        ClusterInput(
            cluster_id=2, source_count=1, first_seen=NOW,
            perspectives=[PerspectiveInput(source_id=2, trust_score=1.0, sentiment=0.6)],
        ),
    ]
    result = compute_perception(clusters, NOW)
    assert result.cluster_count == 2
    assert result.source_count == 2
    assert result.perception > 0


def test_valence_bounded():
    """Valence should always be in [-1, +1]."""
    clusters = [
        ClusterInput(
            cluster_id=i, source_count=3, first_seen=NOW,
            perspectives=[
                PerspectiveInput(source_id=j, trust_score=0.9, sentiment=1.0)
                for j in range(5)
            ],
        )
        for i in range(10)
    ]
    result = compute_perception(clusters, NOW)
    assert -1.0 <= result.valence <= 1.0


# --- compute_perception_momentum ---


def test_momentum_positive():
    assert compute_perception_momentum(3.0, 1.0) == 2.0


def test_momentum_negative():
    assert compute_perception_momentum(-1.0, 2.0) == -3.0


def test_momentum_stable():
    assert compute_perception_momentum(0.5, 0.5) == 0.0
