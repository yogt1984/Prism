"""Shared data models for the news pipeline."""

from datetime import UTC, datetime
from enum import StrEnum

from sqlmodel import Field, Relationship, SQLModel

# --- Enums ---

class Category(StrEnum):
    FINANCE = "finance"
    POLITICS = "politics"
    TECHNOLOGY = "technology"
    SPORTS = "sports"
    CULTURE = "culture"
    SCIENCE = "science"
    HEALTH = "health"
    WORLD = "world"


class BiasLabel(StrEnum):
    LEFT = "left"
    CENTER_LEFT = "center_left"
    CENTER = "center"
    CENTER_RIGHT = "center_right"
    RIGHT = "right"
    UNKNOWN = "unknown"


class BriefingFormat(StrEnum):
    EMAIL = "email"
    JSON_FEED = "json_feed"
    AUDIO_SCRIPT = "audio_script"


class StoryStatus(StrEnum):
    RAW = "raw"
    ANALYZED = "analyzed"


# --- Source Registry ---

class Source(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    url: str = Field(unique=True)
    rss_url: str = ""
    trust_score: float = 0.5  # 0.0 - 1.0, starts neutral
    bias_label: BiasLabel = BiasLabel.UNKNOWN
    categories: str = ""  # comma-separated Category values
    active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- Stories ---

class StoryCluster(SQLModel, table=True):
    """A group of articles covering the same event/topic."""
    id: int | None = Field(default=None, primary_key=True)
    headline: str = ""
    summary: str = ""
    categories: str = ""  # comma-separated
    status: StoryStatus = StoryStatus.RAW
    article_count: int = 0
    prompt_version: str = ""  # analysis prompt version used by A_AI
    quality_score: float = 0.0  # 0.0-1.0, analysis output quality
    resonance_score: float = 0.0  # latest computed resonance (denormalized)
    first_seen: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_updated: datetime = Field(default_factory=lambda: datetime.now(UTC))

    articles: list["Article"] = Relationship(back_populates="cluster")
    perspectives: list["Perspective"] = Relationship(back_populates="cluster")


class Article(SQLModel, table=True):
    """A single article from a single source."""
    id: int | None = Field(default=None, primary_key=True)
    cluster_id: int | None = Field(default=None, foreign_key="storycluster.id")
    source_id: int = Field(foreign_key="source.id")
    title: str
    url: str = Field(unique=True)
    snippet: str = ""
    published_at: datetime | None = None
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    cluster: StoryCluster | None = Relationship(back_populates="articles")


class Perspective(SQLModel, table=True):
    """A distinct framing/perspective on a story cluster, derived by A_AI."""
    id: int | None = Field(default=None, primary_key=True)
    cluster_id: int = Field(foreign_key="storycluster.id")
    source_id: int = Field(foreign_key="source.id")
    summary: str
    sentiment: float = 0.0  # -1.0 (negative) to 1.0 (positive)
    bias_label: BiasLabel = BiasLabel.UNKNOWN
    key_claims: str = ""  # JSON list of claims with source attribution

    cluster: StoryCluster | None = Relationship(back_populates="perspectives")


# --- Users & Personalization ---

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    name: str = ""
    interests: str = ""  # comma-separated Category values
    preferred_format: BriefingFormat = BriefingFormat.EMAIL
    briefing_depth: int = 10  # number of stories per briefing
    is_pro: bool = False
    api_key: str = ""  # deprecated — kept for backward compat, cleared after hashing
    api_key_hash: str = ""  # SHA-256 hash of the API key
    # Stripe subscription
    stripe_customer_id: str = ""  # Stripe Customer ID (cus_xxx)
    stripe_subscription_id: str = ""  # Stripe Subscription ID (sub_xxx)
    pro_since: datetime | None = None  # when Pro was first activated
    pro_until: datetime | None = None  # grace period end after cancellation
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class StripeEvent(SQLModel, table=True):
    """Tracks processed Stripe webhook events for idempotent handling."""
    id: int | None = Field(default=None, primary_key=True)
    event_id: str = Field(unique=True, index=True)  # Stripe event ID (evt_xxx)
    event_type: str = ""  # e.g. "checkout.session.completed"
    user_id: int | None = Field(default=None, foreign_key="user.id")
    processed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Engagement(SQLModel, table=True):
    """Tracks user interaction with stories for personalization feedback."""
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    cluster_id: int = Field(foreign_key="storycluster.id")
    action: str  # "open", "read", "save", "skip"
    read_time_sec: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- Briefings ---

# --- Resonance ---

class TopicResonance(SQLModel, table=True):
    """Computed media-impact score for a story cluster."""
    id: int | None = Field(default=None, primary_key=True)
    cluster_id: int = Field(foreign_key="storycluster.id", index=True)
    resonance: float = 0.0
    momentum: float = 0.0
    peak_resonance: float = 0.0
    mention_count: int = 0
    source_count: int = 0
    authority_weighted_sum: float = 0.0
    breadth: float = 0.0
    window_hours: int = 72
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- Perception Tracking ---


class KeywordTrack(SQLModel, table=True):
    """A keyword or concept to monitor for media perception."""
    id: int | None = Field(default=None, primary_key=True)
    keyword: str = Field(index=True, unique=True)
    aliases: str = ""  # comma-separated synonyms
    category: str = ""  # grouping label
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class KeywordMention(SQLModel, table=True):
    """A tracked keyword detected in an analyzed story cluster."""
    id: int | None = Field(default=None, primary_key=True)
    keyword_id: int = Field(foreign_key="keywordtrack.id", index=True)
    cluster_id: int = Field(foreign_key="storycluster.id", index=True)
    mention_count: int = 0  # total matches across articles
    headline_hit: bool = False  # keyword appears in cluster headline
    source_count: int = 0  # distinct sources mentioning keyword
    weighted_score: float = 0.0  # trust-weighted mention strength
    seen_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PerceptionSnapshot(SQLModel, table=True):
    """Point-in-time perception measurement for a tracked keyword."""
    id: int | None = Field(default=None, primary_key=True)
    keyword_id: int = Field(foreign_key="keywordtrack.id", index=True)
    perception: float = 0.0  # P(K,t) — signed net media pressure
    salience: float = 0.0  # A(K,t) — unsigned attention volume
    valence: float = 0.0  # V(K,t) — direction ∈ [-1, +1]
    momentum: float = 0.0  # dP/dt approximation
    cluster_count: int = 0  # clusters contributing to this snapshot
    source_count: int = 0  # unique sources across all matches
    computed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# --- Briefings ---

class Briefing(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id")
    content_html: str = ""
    content_text: str = ""
    story_count: int = 0
    prompt_version: str = ""  # briefing prompt version used by W_AI
    sent: bool = False
    sent_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
