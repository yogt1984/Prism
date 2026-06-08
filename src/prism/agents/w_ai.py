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

from prism.alerts import AlertLevel, send_alert
from prism.circuit_breaker import CircuitOpenError, claude_breaker
from prism.config import settings
from prism.db import get_engine
from prism.metrics import timed_cycle, tts_failed_total, tts_generated_total
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

AUDIO_SCRIPT_PROMPT = """\
You are writing a spoken-word news briefing script meant to be read aloud or \
fed to a text-to-speech engine.

User interests: {interests}

Stories to cover:
{stories_json}

Rules:
- Write naturally spoken prose — conversational but authoritative.
- NO HTML tags, NO markdown, NO bullet points.
- Open with a brief greeting and date context (e.g. "Good morning. Here's \
your briefing for today.").
- For each story: give a 2-3 sentence summary, then note where sources \
disagree if applicable.
- Use spoken-form attribution: "according to Reuters", "as reported by \
Bloomberg" — never parenthetical "(Source: X)".
- Use transition phrases between stories: "Moving on", "In related news", \
"Also worth noting", "Turning to", "Meanwhile".
- For difficult proper nouns, add phonetic guidance in square brackets \
(e.g. "Yellen [YEL-en]") on first mention only.
- Close with a brief sign-off.
- Target length: ~{word_target} words ({story_count} stories, ~3 minutes \
reading time).
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

    def _format_audio_script(
        self,
        user: User,
        clusters: list[StoryCluster],
        engine: Engine | None = None,
    ) -> str:
        """Generate a spoken-word audio script briefing via Claude."""
        stories_data = self.build_story_data(clusters, engine)
        word_target = max(350, min(550, len(clusters) * 90))

        prompt = AUDIO_SCRIPT_PROMPT.format(
            interests=user.interests,
            stories_json=json.dumps(stories_data, indent=2),
            story_count=len(clusters),
            word_target=word_target,
        )

        response = self._call_claude(prompt)
        return response.content[0].text

    def _format_json_feed(
        self,
        user: User,
        clusters: list[StoryCluster],
        briefing_content: str,
        engine: Engine | None = None,
    ) -> str:
        """Format briefing as a structured JSON feed for API consumers."""
        stories_data = self.build_story_data(clusters, engine)
        items = []
        for cluster, story_data in zip(clusters, stories_data):
            sources = list({
                p.get("bias_label", "unknown"): p.get("summary", "")
                for p in story_data["perspectives"]
            }.keys()) if story_data["perspectives"] else []
            # Collect unique source names from perspectives
            source_names = []
            seen = set()
            for p in story_data["perspectives"]:
                label = p.get("bias_label", "unknown")
                if label not in seen:
                    source_names.append(label)
                    seen.add(label)

            items.append({
                "id": cluster.id,
                "headline": story_data["headline"],
                "summary": story_data["summary"],
                "categories": [c.strip() for c in story_data["categories"].split(",") if c.strip()],
                "perspectives": story_data["perspectives"],
                "sources": source_names,
            })

        feed = {
            "version": "1.0",
            "title": f"Prism Briefing for {user.email}",
            "generated_at": datetime.now(UTC).isoformat(),
            "items": items,
        }
        return json.dumps(feed, indent=2)

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

        # Format-specific content routing
        if fmt == BriefingFormat.JSON_FEED:
            content_html = ""
            content_text = self._format_json_feed(user, clusters, content, e)
        elif fmt == BriefingFormat.AUDIO_SCRIPT:
            content_html = ""
            content_text = self._format_audio_script(user, clusters, e)
        else:
            # Default: EMAIL
            content_html = content
            content_text = ""

        with Session(e) as session:
            briefing = Briefing(
                user_id=user.id,  # type: ignore[arg-type]
                content_html=content_html,
                content_text=content_text,
                story_count=len(clusters),
                prompt_version=BRIEFING_PROMPT_VERSION,
            )
            session.add(briefing)
            session.commit()
            session.refresh(briefing)

            # TTS synthesis for audio briefings
            if fmt == BriefingFormat.AUDIO_SCRIPT:
                self._try_synthesize_audio(briefing, session)

            # Deliver
            if fmt == BriefingFormat.EMAIL:
                sent = self.send_email(user, content)
                if sent:
                    briefing.sent = True
                    briefing.sent_at = datetime.now(UTC)
                    session.add(briefing)
                    session.commit()
            elif fmt == BriefingFormat.JSON_FEED:
                logger.info(
                    "JSON feed briefing for user %s — API-only, no email delivery",
                    user.email,
                )
            elif fmt == BriefingFormat.AUDIO_SCRIPT:
                logger.info(
                    "Audio script briefing for user %s — API-only, no email delivery",
                    user.email,
                )

            logger.info("Created briefing %d for user %s (%d stories)",
                        briefing.id, user.email, len(clusters))
            return briefing

    def _try_synthesize_audio(self, briefing: Briefing, session: Session) -> None:
        """Attempt TTS synthesis. Never raises — failures are logged and alerted."""
        from prism.config import get_settings
        from prism.tts import TTSError
        from prism.tts import synthesize_briefing as _synth

        s = get_settings()

        if not s.openai_api_key:
            logger.info(
                "Skipping TTS for briefing %d — OpenAI API key not configured",
                briefing.id,
            )
            return

        try:
            result = _synth(
                briefing_id=briefing.id,
                text=briefing.content_text,
            )

            # Update briefing with audio metadata
            briefing.audio_path = f"audio/{briefing.id}.mp3"
            briefing.audio_duration_sec = result.duration_sec
            briefing.audio_size_bytes = result.size_bytes
            session.add(briefing)
            session.commit()

            logger.info(
                "TTS complete for briefing %d: %ds, %d bytes",
                briefing.id,
                result.duration_sec,
                result.size_bytes,
            )

        except TTSError as exc:
            logger.error(
                "TTS validation failed for briefing %d: %s", briefing.id, exc
            )
            send_alert(
                f"TTS failed for briefing {briefing.id}: {exc}",
                level=AlertLevel.WARNING,
            )

        except CircuitOpenError as exc:
            logger.warning(
                "TTS circuit open for briefing %d: %s", briefing.id, exc
            )
            send_alert(
                f"TTS circuit breaker open — audio skipped for briefing {briefing.id}",
                level=AlertLevel.WARNING,
            )

        except Exception as exc:
            logger.exception(
                "Unexpected TTS error for briefing %d", briefing.id
            )
            send_alert(
                f"TTS unexpected error for briefing {briefing.id}: {exc}",
                level=AlertLevel.ERROR,
            )
