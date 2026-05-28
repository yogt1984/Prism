"""Resonance — topic media impact score computation.

Pure functions with no DB access. All inputs are passed in for testability.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ResonanceResult:
    """Output of a resonance computation."""
    resonance: float
    mention_count: int
    source_count: int
    authority_weighted_sum: float
    breadth: float


@dataclass(frozen=True)
class ResonanceConfig:
    """Parameters controlling the resonance formula."""
    half_life_hours: float = 24.0
    platform_median: float = 50.0


@dataclass(frozen=True)
class MentionInput:
    """A single article/mention fed into the resonance formula."""
    source_id: int
    trust_score: float          # 0.0–1.0
    reactions: int = 0          # audience reactions (0 = unknown)
    published_at: datetime | None = None


def _decay(age_hours: float, half_life_hours: float) -> float:
    """Exponential decay: returns 1.0 at age 0, 0.5 at half_life."""
    if half_life_hours <= 0:
        return 1.0
    lam = math.log(2) / half_life_hours
    return math.exp(-lam * max(age_hours, 0.0))


def _engagement(reactions: int, platform_median: float) -> float:
    """Log-scaled engagement amplifier. Returns 1.0 when reactions=0."""
    if platform_median <= 0:
        return 1.0
    return 1.0 + math.log2(1.0 + reactions / platform_median)


def compute_resonance(
    mentions: list[MentionInput],
    now: datetime,
    config: ResonanceConfig | None = None,
) -> ResonanceResult:
    """Compute resonance score from a list of mentions.

    Formula: breadth × Σ(trust × engagement × decay)
    """
    if config is None:
        config = ResonanceConfig()

    if not mentions:
        return ResonanceResult(
            resonance=0.0,
            mention_count=0,
            source_count=0,
            authority_weighted_sum=0.0,
            breadth=0.0,
        )

    source_ids: set[int] = set()
    authority_weighted_sum = 0.0
    weighted_sum = 0.0

    for m in mentions:
        source_ids.add(m.source_id)
        authority_weighted_sum += m.trust_score

        # Age in hours
        if m.published_at is not None:
            delta = (now - m.published_at).total_seconds() / 3600.0
        else:
            delta = 0.0

        trust = m.trust_score
        eng = _engagement(m.reactions, config.platform_median)
        dec = _decay(delta, config.half_life_hours)
        weighted_sum += trust * eng * dec

    source_count = len(source_ids)
    breadth = math.log2(1.0 + source_count)
    resonance = breadth * weighted_sum

    return ResonanceResult(
        resonance=resonance,
        mention_count=len(mentions),
        source_count=source_count,
        authority_weighted_sum=authority_weighted_sum,
        breadth=breadth,
    )


def compute_momentum(
    current_resonance: float,
    previous_resonance: float,
) -> float:
    """Momentum = current − previous resonance."""
    return current_resonance - previous_resonance
