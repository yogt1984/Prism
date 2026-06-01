"""Perception Pressure — media perception computation.

Pure functions with no DB access. All inputs are passed in for testability.

The perception metric P(K,t) captures the net media-weighted perception
pressure on a keyword K at time t:

    P(K,t) = salience(K,t) x valence(K,t)

Where:
    salience  = Sigma[ breadth(c) x decay(age_c) ]              (unsigned)
    valence   = Sigma[ breadth(c) x decay(age_c) x Sigma[ trust(p) x sentiment(p) ] ]
                / Sigma[ breadth(c) x decay(age_c) x Sigma[ trust(p) ] ]    (in [-1, +1])

P > 0: net positive media framing
P < 0: net negative media framing
|P| large: strong, broad, authoritative, fresh coverage
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class PerceptionConfig:
    """Parameters controlling the perception formula."""
    half_life_hours: float = 24.0


@dataclass(frozen=True)
class PerspectiveInput:
    """A single perspective fed into the perception formula."""
    source_id: int
    trust_score: float  # 0.0-1.0
    sentiment: float  # -1.0 to +1.0


@dataclass(frozen=True)
class ClusterInput:
    """A story cluster mentioning the tracked keyword."""
    cluster_id: int
    source_count: int
    first_seen: datetime | None = None
    perspectives: list[PerspectiveInput] = field(default_factory=list)


@dataclass(frozen=True)
class PerceptionResult:
    """Output of a perception computation."""
    perception: float  # P(K,t) — the single signed float
    salience: float  # A(K,t) — unsigned attention volume
    valence: float  # V(K,t) — direction in [-1, +1]
    cluster_count: int
    source_count: int


@dataclass(frozen=True)
class MentionResult:
    """Output of keyword scanning against a single cluster."""
    cluster_id: int
    mention_count: int
    headline_hit: bool
    source_count: int
    weighted_score: float


def _decay(age_hours: float, half_life_hours: float) -> float:
    """Exponential decay: returns 1.0 at age 0, 0.5 at half_life."""
    if half_life_hours <= 0:
        return 1.0
    lam = math.log(2) / half_life_hours
    return math.exp(-lam * max(age_hours, 0.0))


def _age_hours(first_seen: datetime | None, now: datetime) -> float:
    """Compute age in hours, handling timezone mismatches."""
    if first_seen is None:
        return 0.0
    fs = first_seen
    n = now
    if fs.tzinfo is None and n.tzinfo is not None:
        fs = fs.replace(tzinfo=n.tzinfo)
    elif fs.tzinfo is not None and n.tzinfo is None:
        n = n.replace(tzinfo=fs.tzinfo)
    return max((n - fs).total_seconds() / 3600.0, 0.0)


def compute_perception(
    clusters: list[ClusterInput],
    now: datetime,
    config: PerceptionConfig | None = None,
) -> PerceptionResult:
    """Compute perception pressure from clusters mentioning a keyword.

    Formula: P = salience x valence
    Where salience = sum of breadth*decay across clusters,
    and valence = trust-weighted average sentiment.
    """
    if config is None:
        config = PerceptionConfig()

    if not clusters:
        return PerceptionResult(
            perception=0.0,
            salience=0.0,
            valence=0.0,
            cluster_count=0,
            source_count=0,
        )

    salience = 0.0
    weighted_sentiment_sum = 0.0
    weight_sum = 0.0
    all_sources: set[int] = set()

    for c in clusters:
        age = _age_hours(c.first_seen, now)
        decay = _decay(age, config.half_life_hours)
        breadth = math.log2(1.0 + c.source_count)
        cluster_weight = breadth * decay

        salience += cluster_weight

        for p in c.perspectives:
            all_sources.add(p.source_id)
            w = p.trust_score * cluster_weight
            weighted_sentiment_sum += w * p.sentiment
            weight_sum += w

    valence = weighted_sentiment_sum / weight_sum if weight_sum > 0 else 0.0
    perception = salience * valence

    return PerceptionResult(
        perception=perception,
        salience=salience,
        valence=valence,
        cluster_count=len(clusters),
        source_count=len(all_sources),
    )


def compute_perception_momentum(
    current: float,
    previous: float,
) -> float:
    """Momentum = current - previous perception."""
    return current - previous


def scan_text_for_keywords(
    text: str,
    terms: list[str],
) -> int:
    """Count word-boundary matches of any term in text. Case-insensitive."""
    if not text or not terms:
        return 0
    count = 0
    text_lower = text.lower()
    for term in terms:
        pattern = re.compile(r"\b" + re.escape(term.lower()) + r"\b")
        count += len(pattern.findall(text_lower))
    return count


def scan_cluster_for_keyword(
    headline: str,
    article_titles: list[str],
    source_ids: list[int],
    trust_map: dict[int, float],
    keyword: str,
    aliases: list[str],
    cluster_id: int,
) -> MentionResult | None:
    """Scan a cluster's headline + article titles for a keyword.

    Returns None if no matches found.
    """
    terms = [keyword] + [a for a in aliases if a]

    headline_count = scan_text_for_keywords(headline, terms)
    headline_hit = headline_count > 0

    total_count = headline_count
    matching_sources: set[int] = set()
    weighted_score = 0.0

    for title, sid in zip(article_titles, source_ids):
        hits = scan_text_for_keywords(title, terms)
        if hits > 0:
            total_count += hits
            matching_sources.add(sid)
            weighted_score += trust_map.get(sid, 0.5) * hits

    if headline_hit:
        # Headline hit counts toward source diversity but we don't have
        # a single source for the cluster headline, so skip source counting.
        pass

    if total_count == 0:
        return None

    return MentionResult(
        cluster_id=cluster_id,
        mention_count=total_count,
        headline_hit=headline_hit,
        source_count=len(matching_sources),
        weighted_score=weighted_score,
    )
