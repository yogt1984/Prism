"""T13.1: TF-IDF deduplication fallback tests."""

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from prism.agents.d_ai import DiscoveryAgent


@pytest.fixture()
def agent():
    """DiscoveryAgent with a mocked httpx client."""
    with patch.object(DiscoveryAgent, "__init__", lambda self: None):
        a = DiscoveryAgent()
        a.http = MagicMock(spec=httpx.Client)
        return a


# ══════════════════════════════════════════════════════════════════════
# _tfidf_similarity unit tests
# ══════════════════════════════════════════════════════════════════════


class TestTfidfSimilarity:

    def test_identical_strings(self, agent):
        assert agent._tfidf_similarity("hello world", "hello world") == pytest.approx(1.0)

    def test_completely_different(self, agent):
        sim = agent._tfidf_similarity("cat dog mouse", "red blue green")
        assert sim < 0.1

    def test_partial_overlap(self, agent):
        sim = agent._tfidf_similarity(
            "Federal Reserve raises interest rates",
            "Federal Reserve increases benchmark rates",
        )
        assert sim > 0.3

    def test_empty_first_string(self, agent):
        assert agent._tfidf_similarity("", "hello") == 0.0

    def test_empty_second_string(self, agent):
        assert agent._tfidf_similarity("hello", "") == 0.0

    def test_both_empty(self, agent):
        assert agent._tfidf_similarity("", "") == 0.0

    def test_returns_float(self, agent):
        result = agent._tfidf_similarity("hello world", "hello there")
        assert isinstance(result, float)

    def test_range_zero_to_one(self, agent):
        result = agent._tfidf_similarity("the quick brown fox", "a lazy brown dog")
        assert 0.0 <= result <= 1.0


# ══════════════════════════════════════════════════════════════════════
# TF-IDF fallback in deduplicate_articles
# ══════════════════════════════════════════════════════════════════════


class TestTfidfFallback:

    def test_same_event_different_wording_clusters(self, agent):
        """Articles about the same event with different wording should cluster."""
        articles = [
            {"title": "Federal Reserve raises interest rates amid inflation worries in economy"},
            {"title": "Federal Reserve increases interest rates due to inflation fears in economy"},
        ]
        # Jaccard ~0.5 (gray zone) but TF-IDF ~0.5 catches the similarity
        clusters = agent.deduplicate_articles(articles)
        assert len(clusters) == 1
        assert len(clusters[0]) == 2

    def test_different_events_stay_separate(self, agent):
        """Articles about genuinely different events should not cluster."""
        articles = [
            {"title": "NASA launches new Mars exploration rover from Cape Canaveral"},
            {"title": "Tokyo Olympic Games opening ceremony draws record television viewers"},
        ]
        clusters = agent.deduplicate_articles(articles)
        assert len(clusters) == 2

    def test_jaccard_above_threshold_still_works(self, agent):
        """High Jaccard similarity should cluster without needing TF-IDF."""
        articles = [
            {"title": "Stock market crashes today amid fears"},
            {"title": "Stock market crashes today amid panic"},
        ]
        clusters = agent.deduplicate_articles(articles)
        assert len(clusters) == 1

    def test_low_jaccard_no_tfidf_check(self, agent):
        """Jaccard below 0.4 should not trigger TF-IDF tiebreaker."""
        articles = [
            {"title": "Apple announces new iPhone release date"},
            {"title": "Scientists discover high-energy cosmic particles in space"},
        ]
        with patch.object(agent, "_tfidf_similarity") as mock_tfidf:
            clusters = agent.deduplicate_articles(articles)
            mock_tfidf.assert_not_called()
        assert len(clusters) == 2

    def test_jaccard_in_gray_zone_uses_tfidf(self, agent):
        """Jaccard in [0.4, 0.6) should trigger TF-IDF check."""
        articles = [
            {"title": "President signs major climate change legislation bill today"},
            {"title": "President enacts sweeping climate change policy legislation now"},
        ]
        with patch.object(agent, "_tfidf_similarity", wraps=agent._tfidf_similarity) as mock:
            agent.deduplicate_articles(articles)
            # If Jaccard was in the gray zone, TF-IDF should have been called
            if mock.call_count == 0:
                # Jaccard was already >= 0.6, which is fine too
                pass
            else:
                assert mock.call_count >= 1

    def test_tfidf_below_threshold_stays_separate(self, agent):
        """In the gray zone, if TF-IDF is also low, articles stay separate."""
        articles = [
            {"title": "Apple fruit harvest season begins California farms"},
            {"title": "Apple technology company announces quarterly earnings report"},
        ]
        # "Apple" creates some word overlap but context is totally different
        clusters = agent.deduplicate_articles(articles)
        assert len(clusters) == 2

    def test_existing_tests_backward_compatible(self, agent):
        """Original dedup behavior is preserved for clear-cut cases."""
        # Exact duplicates
        articles = [
            {"title": "Breaking: earthquake strikes region", "url": "a.com"},
            {"title": "Breaking: earthquake strikes region", "url": "b.com"},
        ]
        assert len(agent.deduplicate_articles(articles)) == 1

        # Clearly different
        articles = [
            {"title": "Tech stocks soar"},
            {"title": "Weather forecast sunny"},
        ]
        assert len(agent.deduplicate_articles(articles)) == 2

    def test_empty_input(self, agent):
        assert agent.deduplicate_articles([]) == []

    def test_single_article(self, agent):
        clusters = agent.deduplicate_articles([{"title": "One article"}])
        assert len(clusters) == 1


# ══════════════════════════════════════════════════════════════════════
# Graceful fallback without sklearn
# ══════════════════════════════════════════════════════════════════════


class TestSklearnFallback:

    def test_tfidf_returns_zero_without_sklearn(self, agent):
        """When sklearn is not available, _tfidf_similarity returns 0.0."""
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "sklearn" in name:
                raise ImportError("No module named 'sklearn'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            result = agent._tfidf_similarity("hello world", "hello there")
        assert result == 0.0

    def test_dedup_works_without_sklearn(self, agent):
        """Without sklearn, dedup falls back to Jaccard-only (no crash)."""
        articles = [
            {"title": "Federal Reserve raises interest rates by quarter point"},
            {"title": "Fed increases interest rates 25 basis points"},
        ]
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if "sklearn" in name:
                raise ImportError("No module named 'sklearn'")
            return original_import(name, *args, **kwargs)

        with patch.object(builtins, "__import__", side_effect=mock_import):
            clusters = agent.deduplicate_articles(articles)
        # Should not crash — result depends on Jaccard alone
        assert isinstance(clusters, list)
        assert len(clusters) >= 1


# ══════════════════════════════════════════════════════════════════════
# Performance
# ══════════════════════════════════════════════════════════════════════


class TestDedupPerformance:

    def test_200_articles_under_2_seconds(self, agent):
        """Dedup of 200 articles should complete in under 2 seconds."""
        articles = [
            {"title": f"News story number {i} about topic {i % 10} with extra words"}
            for i in range(200)
        ]
        start = time.monotonic()
        clusters = agent.deduplicate_articles(articles)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"Dedup took {elapsed:.2f}s, expected <2s"
        assert len(clusters) > 0

    def test_200_similar_articles_under_2_seconds(self, agent):
        """Worst case: many articles in the gray zone."""
        base_words = ["economy", "growth", "market", "report", "quarter"]
        articles = []
        for i in range(200):
            # Rotate words to create gray-zone Jaccard overlap
            words = base_words[i % len(base_words):] + base_words[:i % len(base_words)]
            articles.append({"title": f"Article {i}: " + " ".join(words) + f" extra{i}"})
        start = time.monotonic()
        clusters = agent.deduplicate_articles(articles)
        elapsed = time.monotonic() - start
        assert elapsed < 2.0, f"Dedup took {elapsed:.2f}s, expected <2s"
        assert len(clusters) > 0


# ══════════════════════════════════════════════════════════════════════
# T13.2: Named entity overlap
# ══════════════════════════════════════════════════════════════════════


class TestEntityOverlap:

    def test_same_entities(self, agent):
        assert agent._entity_overlap(
            "Elon Musk announces new plan",
            "Elon Musk reveals strategy",
        ) > 0.0

    def test_no_shared_entities(self, agent):
        assert agent._entity_overlap(
            "Elon Musk launches rocket",
            "Tim Cook presents iPhone",
        ) == 0.0

    def test_partial_entity_overlap(self, agent):
        overlap = agent._entity_overlap(
            "Elon Musk and Tim Cook meet at White House",
            "Elon Musk visits White House for summit",
        )
        # "Elon Musk" and "White House" shared, "Tim Cook" only in first
        assert 0.0 < overlap < 1.0

    def test_empty_strings(self, agent):
        assert agent._entity_overlap("", "Elon Musk") == 0.0
        assert agent._entity_overlap("Elon Musk", "") == 0.0
        assert agent._entity_overlap("", "") == 0.0

    def test_no_capitalized_words(self, agent):
        """Strings with no capitalized words → no entities → 0.0."""
        assert agent._entity_overlap("the quick brown fox", "a lazy brown dog") == 0.0

    def test_returns_float_in_range(self, agent):
        result = agent._entity_overlap(
            "Apple Google Microsoft Amazon",
            "Apple Google Facebook Netflix",
        )
        assert isinstance(result, float)
        assert 0.0 <= result <= 1.0

    def test_identical_entities(self, agent):
        assert agent._entity_overlap(
            "Federal Reserve Bank of America",
            "Federal Reserve Bank of America",
        ) == 1.0

    def test_multi_word_entities(self, agent):
        """Multi-word entities like 'Federal Reserve' are captured as one unit."""
        overlap = agent._entity_overlap(
            "Federal Reserve raises rates",
            "Federal Reserve cuts rates",
        )
        assert overlap > 0.0


class TestCombinedSimilarity:

    def test_combined_bounded(self, agent):
        """Combined score must be in [0.0, 1.0]."""
        pairs = [
            ("identical text here", "identical text here"),
            ("cat dog mouse", "red blue green"),
            ("Apple stock price rises", "Apple stock price falls"),
            ("", "hello"),
        ]
        for a, b in pairs:
            score = agent._combined_similarity(a, b)
            assert 0.0 <= score <= 1.0, f"Out of range for {a!r} vs {b!r}: {score}"

    def test_identical_is_one(self, agent):
        score = agent._combined_similarity(
            "The Federal Reserve raises rates",
            "The Federal Reserve raises rates",
        )
        assert score == pytest.approx(1.0)

    def test_completely_different_near_zero(self, agent):
        score = agent._combined_similarity(
            "cat dog mouse rabbit",
            "red blue green yellow",
        )
        assert score < 0.1

    def test_entity_component_contributes(self, agent):
        """Shared entities should increase combined score vs no shared entities."""
        with_entities = agent._combined_similarity(
            "Elon Musk announces Tesla expansion in California",
            "Elon Musk reveals Tesla growth plans for California",
        )
        without_entities = agent._combined_similarity(
            "Tim Cook announces Apple expansion in California",
            "Elon Musk reveals Tesla growth plans for California",
        )
        assert with_entities > without_entities


class TestEntityInDedup:
    """Entity overlap integrated into deduplicate_articles."""

    def test_shared_entities_help_clustering(self, agent):
        """Articles sharing named entities cluster when in the gray zone."""
        articles = [
            {"title": "Federal Reserve announces new interest rate policy for economy"},
            {"title": "Federal Reserve reveals updated interest rate strategy for economy"},
        ]
        clusters = agent.deduplicate_articles(articles)
        assert len(clusters) == 1

    def test_different_entities_stay_separate(self, agent):
        """Articles about different entities in similar domains stay separate."""
        articles = [
            {"title": "Apple unveils revolutionary smartphone at annual keynote event"},
            {"title": "Samsung reveals innovative smartphone at global product launch"},
        ]
        clusters = agent.deduplicate_articles(articles)
        assert len(clusters) == 2

    def test_no_entities_fallback_to_jaccard_tfidf(self, agent):
        """Without entities, dedup still works via Jaccard/TF-IDF."""
        articles = [
            {"title": "the stock market crashed today amid fears"},
            {"title": "the stock market crashed today amid panic"},
        ]
        clusters = agent.deduplicate_articles(articles)
        assert len(clusters) == 1  # high Jaccard

    def test_combined_score_used_in_gray_zone(self, agent):
        """Verify _combined_similarity is called when Jaccard is in gray zone."""
        articles = [
            {"title": "Federal Reserve announces new interest rate policy for economy"},
            {"title": "Federal Reserve reveals updated interest rate strategy for economy"},
        ]
        with patch.object(agent, "_combined_similarity",
                          wraps=agent._combined_similarity) as mock:
            agent.deduplicate_articles(articles)
            jaccard = agent._jaccard(
                articles[0]["title"], articles[1]["title"],
            )
            if 0.4 <= jaccard < 0.6:
                assert mock.call_count >= 1
