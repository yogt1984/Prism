"""W_AI — Writer Agent.

Generates personalized briefings from selected stories.
Formats for email (HTML), JSON feed, or audio script.
Every claim is attributed to its source — no orphaned statements.
"""

import json
import logging
from datetime import UTC, datetime

import anthropic
import resend
from sqlalchemy import Engine
from sqlmodel import Session, select

from prism.circuit_breaker import claude_breaker
from prism.config import settings
from prism.db import get_engine
from prism.metrics import timed_cycle
from prism.models import (
    Briefing,
    BriefingFormat,
    Perspective,
    StoryCluster,
    User,
)
from prism.retry import retry_on_transient

logger = logging.getLogger(__name__)

# v2: added explicit (Source:) attribution requirement per claim,
#     format-conditional HTML/prose, word count target.
BRIEFING_PROMPT_VERSION = "2"

BRIEFING_PROMPT = """\
You are a news briefing writer. Generate a concise, personalized news briefing.

User interests: {interests}
Format: {format}

Stories to include (each with multiple perspectives):
{stories_json}

Rules:
- Lead with the most important story
- For each story: 2-3 sentence summary, then note where sources diverge
- EVERY factual claim must end with (Source: <outlet name>)
- Tone: clear, direct, informative — not sensational
- If email format: use clean HTML with <h2> for story headers, <p> for text
- If audio_script: write naturally spoken prose, no HTML
- End with a brief "Also worth watching" section for lower-priority items
- Total length: ~800 words for {story_count} stories
"""


class WriterAgent:
    def __init__(self) -> None:
        self.client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        resend.api_key = settings.resend_api_key

    def build_story_data(
        self, clusters: list[StoryCluster], engine: Engine | None = None,
    ) -> list[dict]:
        """Build rich story data including perspectives for the prompt."""
        e = engine or get_engine()
        stories = []
        with Session(e) as session:
            for cluster in clusters:
                perspectives = session.exec(
                    select(Perspective).where(Perspective.cluster_id == cluster.id)
                ).all()

                stories.append({
                    "headline": cluster.headline,
                    "summary": cluster.summary,
                    "categories": cluster.categories,
                    "perspectives": [
                        {
                            "summary": p.summary,
                            "sentiment": p.sentiment,
                            "bias_label": p.bias_label,
                            "key_claims": json.loads(p.key_claims) if p.key_claims else [],
                        }
                        for p in perspectives
                    ],
                })
        return stories

    def generate_briefing(
        self, user: User, clusters: list[StoryCluster],
        engine: Engine | None = None,
    ) -> str:
        """Generate a briefing for a user from their selected stories."""
        stories_data = self.build_story_data(clusters, engine)

        prompt = BRIEFING_PROMPT.format(
            interests=user.interests,
            format=user.preferred_format,
            stories_json=json.dumps(stories_data, indent=2),
            story_count=len(clusters),
        )

        response = self._call_claude(prompt)
        return response.content[0].text

    @claude_breaker
    @retry_on_transient(max_retries=3, base_delay=2.0)
    def _call_claude(self, prompt: str):  # type: ignore[no-untyped-def]
        """Call Claude API with retry on transient failures."""
        return self.client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

    @staticmethod
    @retry_on_transient(max_retries=3, base_delay=2.0, extra_exceptions=(Exception,))
    def _send_via_resend(payload: dict) -> None:
        """Send email via Resend with retry on transient failures."""
        resend.Emails.send(payload)

    def send_email(self, user: User, content_html: str) -> bool:
        """Send briefing via email using Resend."""
        try:
            self._send_via_resend({
                "from": settings.briefing_from_email,
                "to": [user.email],
                "subject": f"Your News Briefing — {datetime.now(UTC).strftime('%B %d, %Y')}",
                "html": content_html,
            })
            logger.info("Sent briefing email to %s", user.email)
            return True
        except Exception:
            logger.exception("Failed to send email to %s", user.email)
            return False

    @timed_cycle("briefing")
    def create_and_send(
        self, user: User, clusters: list[StoryCluster],
        engine: Engine | None = None,
    ) -> Briefing | None:
        """Full pipeline: generate briefing, store, and deliver."""
        if not clusters:
            logger.info("No stories for user %s, skipping", user.email)
            return None

        # Tier enforcement: free users always get email format
        fmt = user.preferred_format
        if not user.is_pro and fmt != BriefingFormat.EMAIL:
            logger.info(
                "Free user %s requested %s, falling back to email",
                user.email, fmt,
            )
            fmt = BriefingFormat.EMAIL

        e = engine or get_engine()
        content = self.generate_briefing(user, clusters, e)

        with Session(e) as session:
            briefing = Briefing(
                user_id=user.id,  # type: ignore[arg-type]
                content_html=content if fmt == BriefingFormat.EMAIL else "",
                content_text=content if fmt != BriefingFormat.EMAIL else "",
                story_count=len(clusters),
                prompt_version=BRIEFING_PROMPT_VERSION,
            )
            session.add(briefing)
            session.commit()
            session.refresh(briefing)

            # Deliver
            if fmt == BriefingFormat.EMAIL:
                sent = self.send_email(user, content)
                if sent:
                    briefing.sent = True
                    briefing.sent_at = datetime.now(UTC)
                    session.add(briefing)
                    session.commit()
            else:
                logger.info(
                    "Skipping delivery for user %s (format=%s, not yet supported)",
                    user.email, fmt,
                )

            logger.info("Created briefing %d for user %s (%d stories)",
                        briefing.id, user.email, len(clusters))
            return briefing
