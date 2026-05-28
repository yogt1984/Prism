"""A_AI — Analysis Agent.

Analyzes story clusters: summarizes, extracts perspectives,
detects sentiment/bias, and categorizes by topic.
"""

import json
import logging
import time
from datetime import UTC, datetime

import anthropic
from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.circuit_breaker import claude_breaker
from prism.config import settings
from prism.db import get_engine
from prism.metrics import resonance_computed_total, timed_cycle
from prism.models import (
    Article,
    BiasLabel,
    Perspective,
    Source,
    StoryCluster,
    StoryStatus,
    TopicResonance,
)
from prism.resonance import MentionInput, ResonanceConfig, compute_momentum, compute_resonance
from prism.retry import retry_on_transient

logger = logging.getLogger(__name__)

# v2: added explicit JSON-only instruction, required (Source:) in claims,
#     restricted categories to fixed set.
ANALYSIS_PROMPT_VERSION = "2"

ANALYSIS_PROMPT = """\
You are a news analyst. Given a cluster of articles about the same event,
produce a structured analysis.

Articles:
{articles_json}

Respond with valid JSON only (no markdown fences):
{{
    "headline": "concise neutral headline for this story",
    "summary": "2-3 sentence neutral summary of the core facts",
    "categories": ["list", "of", "categories"],
    "perspectives": [
        {{
            "source_name": "name of the outlet",
            "source_id": <source_id>,
            "summary": "how this source frames the story",
            "sentiment": <float -1.0 to 1.0>,
            "bias_label": "left|center_left|center|center_right|right|unknown",
            "key_claims": ["claim 1 (Source: outlet)", "claim 2 (Source: outlet)"]
        }}
    ]
}}

Rules:
- Be factual. Do not editorialize.
- Every claim must be traceable to a specific source article.
- If sources disagree on facts, note the disagreement explicitly.
- Categories must be from: finance, politics, technology, sports, \
culture, science, health, world.
"""

_VALID_BIAS_LABELS = {b.value for b in BiasLabel}


class AnalysisAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    @staticmethod
    def _validate_analysis(result: dict) -> list[str]:
        """Validate analysis output quality, returning a list of issues."""
        issues: list[str] = []

        # Check summary length
        summary = result.get("summary", "")
        if len(summary) < 50:
            issues.append(f"Summary too short ({len(summary)} chars, min 50)")
        elif len(summary) > 500:
            issues.append(f"Summary too long ({len(summary)} chars, max 500)")

        # Check perspectives count
        perspectives = result.get("perspectives", [])
        if len(perspectives) < 2:
            issues.append(f"Too few perspectives ({len(perspectives)}, min 2)")

        # Check each perspective
        seen_source_ids: set[int] = set()
        for i, p in enumerate(perspectives):
            # key_claims non-empty
            claims = p.get("key_claims", [])
            if not claims:
                issues.append(f"Perspective {i} has empty key_claims")

            # sentiment in range
            sentiment = p.get("sentiment", 0.0)
            try:
                s_val = float(sentiment)
                if s_val < -1.0 or s_val > 1.0:
                    issues.append(f"Perspective {i} sentiment {s_val} out of range [-1.0, 1.0]")
            except (TypeError, ValueError):
                issues.append(f"Perspective {i} has invalid sentiment value")

            # duplicate source_ids
            sid = p.get("source_id")
            if sid is not None:
                if sid in seen_source_ids:
                    issues.append(f"Duplicate source_id {sid} in perspectives")
                seen_source_ids.add(sid)

        return issues

    @staticmethod
    def _compute_quality_score(issues: list[str], total_checks: int) -> float:
        """Compute quality score as ratio of passed checks."""
        if total_checks == 0:
            return 0.0
        passed = max(0, total_checks - len(issues))
        return round(passed / total_checks, 2)

    @staticmethod
    def _truncate_articles(
        articles_data: list[dict], max_tokens: int,
    ) -> list[dict]:
        """Truncate article snippets to fit within token budget."""
        char_budget = max_tokens * 4  # ~4 chars per token
        base_chars = sum(
            len(a["title"]) + len(a["url"]) + 50 for a in articles_data
        )
        snippet_budget = max(0, char_budget - base_chars)
        per_article = snippet_budget // max(len(articles_data), 1)

        for a in articles_data:
            if len(a["snippet"]) > per_article:
                a["snippet"] = a["snippet"][:per_article] + "..."
        return articles_data

    @staticmethod
    def _clamp_sentiment(value: float) -> float:
        return max(-1.0, min(1.0, value))

    @staticmethod
    def _safe_bias_label(value: str) -> BiasLabel:
        if value in _VALID_BIAS_LABELS:
            return BiasLabel(value)
        return BiasLabel.UNKNOWN

    @claude_breaker
    @retry_on_transient(max_retries=3, base_delay=2.0)
    def _call_claude(self, prompt: str):  # type: ignore[no-untyped-def]
        """Call Claude API with retry on transient failures."""
        return self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

    def analyze_cluster(
        self, cluster_id: int, engine: Engine | None = None,
    ) -> None:
        """Analyze a story cluster and store perspectives."""
        e = engine or get_engine()
        with Session(e) as session:
            cluster = session.get(StoryCluster, cluster_id)
            if cluster is None:
                logger.warning("Cluster %d not found", cluster_id)
                return

            articles = session.exec(
                select(Article).where(Article.cluster_id == cluster_id)
            ).all()

            if not articles:
                logger.warning(
                    "Cluster %d has no articles, skipping", cluster_id,
                )
                return

            # Keep top 15 articles, prioritizing higher-trust sources
            source_ids = {a.source_id for a in articles}
            trust_map = {
                s.id: s.trust_score
                for s in session.exec(
                    select(Source).where(Source.id.in_(source_ids))  # type: ignore[union-attr]
                ).all()
            }
            sorted_articles = sorted(
                articles,
                key=lambda a: trust_map.get(a.source_id, 0.0),
                reverse=True,
            )[:15]

            articles_data = [
                {
                    "source_id": a.source_id,
                    "title": a.title,
                    "url": a.url,
                    "snippet": a.snippet,
                }
                for a in sorted_articles
            ]
            articles_data = self._truncate_articles(
                articles_data, settings.max_input_tokens,
            )

            prompt = ANALYSIS_PROMPT.format(
                articles_json=json.dumps(articles_data, indent=2),
            )

            response = self._call_claude(prompt)

            try:
                result = json.loads(response.content[0].text)
            except (json.JSONDecodeError, IndexError):
                logger.error(
                    "Failed to parse analysis response for cluster %d",
                    cluster_id,
                )
                return

            # Validate output quality
            issues = self._validate_analysis(result)
            # Total checks: summary length, perspectives count,
            # + per-perspective: key_claims, sentiment, duplicate source_id
            n_perspectives = len(result.get("perspectives", []))
            total_checks = 2 + n_perspectives * 3  # 2 global + 3 per perspective
            quality_score = self._compute_quality_score(issues, total_checks)
            if issues:
                logger.warning(
                    "Quality issues for cluster %d (score=%.2f): %s",
                    cluster_id, quality_score, "; ".join(issues),
                )

            # Update cluster
            cluster.headline = result.get("headline", cluster.headline)
            cluster.summary = result.get("summary", "")
            cluster.categories = ",".join(result.get("categories", []))
            cluster.status = StoryStatus.ANALYZED
            cluster.prompt_version = ANALYSIS_PROMPT_VERSION
            cluster.quality_score = quality_score

            # Store perspectives (capped to config limit)
            perspectives_raw = result.get("perspectives", [])
            perspectives_raw = perspectives_raw[:settings.max_perspectives_per_story]
            for p in perspectives_raw:
                # Validate source_id exists
                sid = p.get("source_id", articles[0].source_id)
                if session.get(Source, sid) is None:
                    sid = articles[0].source_id

                perspective = Perspective(
                    cluster_id=cluster_id,
                    source_id=sid,
                    summary=p.get("summary", ""),
                    sentiment=self._clamp_sentiment(
                        float(p.get("sentiment", 0.0)),
                    ),
                    bias_label=self._safe_bias_label(
                        p.get("bias_label", "unknown"),
                    ),
                    key_claims=json.dumps(p.get("key_claims", [])),
                )
                session.add(perspective)

            session.add(cluster)
            session.commit()
            logger.info(
                "Analyzed cluster %d: %s (%d perspectives)",
                cluster_id,
                cluster.headline,
                len(result.get("perspectives", [])),
            )

            # Compute resonance (failure must not block analysis)
            try:
                self._update_resonance(session, cluster, articles, trust_map)
            except Exception:
                logger.exception(
                    "Resonance computation failed for cluster %d", cluster_id,
                )

    @staticmethod
    def _update_resonance(
        session: Session,
        cluster: StoryCluster,
        articles: list[Article],
        trust_map: dict[int, float],
    ) -> None:
        """Compute and upsert resonance for a cluster."""
        now = datetime.now(UTC)
        config = ResonanceConfig(
            half_life_hours=float(settings.resonance_half_life_hours),
            platform_median=float(settings.resonance_platform_median),
        )

        mentions = [
            MentionInput(
                source_id=a.source_id,
                trust_score=trust_map.get(a.source_id, 0.5),
                reactions=0,
                published_at=a.published_at or a.fetched_at,
            )
            for a in articles
        ]

        result = compute_resonance(mentions, now, config)

        # Fetch existing row for momentum + peak
        existing = session.exec(
            select(TopicResonance)
            .where(TopicResonance.cluster_id == cluster.id)
            .order_by(TopicResonance.computed_at.desc())  # type: ignore[union-attr]
        ).first()

        previous_resonance = existing.resonance if existing else 0.0
        momentum = compute_momentum(result.resonance, previous_resonance)
        peak = max(result.resonance, existing.peak_resonance if existing else 0.0)

        if existing:
            existing.resonance = result.resonance
            existing.momentum = momentum
            existing.peak_resonance = peak
            existing.mention_count = result.mention_count
            existing.source_count = result.source_count
            existing.authority_weighted_sum = result.authority_weighted_sum
            existing.breadth = result.breadth
            existing.window_hours = settings.resonance_window_hours
            existing.computed_at = now
            session.add(existing)
        else:
            tr = TopicResonance(
                cluster_id=cluster.id,
                resonance=result.resonance,
                momentum=momentum,
                peak_resonance=peak,
                mention_count=result.mention_count,
                source_count=result.source_count,
                authority_weighted_sum=result.authority_weighted_sum,
                breadth=result.breadth,
                window_hours=settings.resonance_window_hours,
                computed_at=now,
            )
            session.add(tr)

        cluster.resonance_score = result.resonance
        session.add(cluster)
        session.commit()
        resonance_computed_total.inc()

    @timed_cycle("analysis")
    def process_pending(self, engine: Engine | None = None) -> None:
        """Analyze all raw (unanalyzed) story clusters."""
        e = engine or get_engine()
        with Session(e) as session:
            clusters = session.exec(
                select(StoryCluster).where(
                    StoryCluster.status == StoryStatus.RAW,
                )
            ).all()
            cluster_ids = [c.id for c in clusters]

        logger.info("Found %d raw clusters to analyze", len(cluster_ids))
        for i, cid in enumerate(cluster_ids):
            if i > 0:
                time.sleep(1)
            try:
                self.analyze_cluster(cid, e)
            except Exception:
                logger.exception("Failed to analyze cluster %d", cid)
