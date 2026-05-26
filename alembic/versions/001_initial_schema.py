"""Initial schema — all tables from SQLModel metadata.

Revision ID: 001
Revises: None
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "source",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String, nullable=False),
        sa.Column("url", sa.String, nullable=False, unique=True),
        sa.Column("rss_url", sa.String, nullable=False, server_default=""),
        sa.Column("trust_score", sa.Float, nullable=False, server_default="0.5"),
        sa.Column("bias_label", sa.String, nullable=False, server_default="unknown"),
        sa.Column("categories", sa.String, nullable=False, server_default=""),
        sa.Column("active", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_source_name", "source", ["name"])

    op.create_table(
        "storycluster",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("headline", sa.String, nullable=False, server_default=""),
        sa.Column("summary", sa.String, nullable=False, server_default=""),
        sa.Column("categories", sa.String, nullable=False, server_default=""),
        sa.Column("status", sa.String, nullable=False, server_default="raw"),
        sa.Column("article_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("first_seen", sa.DateTime, nullable=False),
        sa.Column("last_updated", sa.DateTime, nullable=False),
    )

    op.create_table(
        "article",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("storycluster.id")),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("source.id"), nullable=False),
        sa.Column("title", sa.String, nullable=False),
        sa.Column("url", sa.String, nullable=False, unique=True),
        sa.Column("snippet", sa.String, nullable=False, server_default=""),
        sa.Column("published_at", sa.DateTime, nullable=True),
        sa.Column("fetched_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "perspective",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("storycluster.id"), nullable=False),
        sa.Column("source_id", sa.Integer, sa.ForeignKey("source.id"), nullable=False),
        sa.Column("summary", sa.String, nullable=False),
        sa.Column("sentiment", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("bias_label", sa.String, nullable=False, server_default="unknown"),
        sa.Column("key_claims", sa.String, nullable=False, server_default=""),
    )

    op.create_table(
        "user",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String, nullable=False, unique=True),
        sa.Column("name", sa.String, nullable=False, server_default=""),
        sa.Column("interests", sa.String, nullable=False, server_default=""),
        sa.Column("preferred_format", sa.String, nullable=False, server_default="email"),
        sa.Column("briefing_depth", sa.Integer, nullable=False, server_default="10"),
        sa.Column("is_pro", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("api_key", sa.String, nullable=False, server_default=""),
        sa.Column("api_key_hash", sa.String, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )
    op.create_index("ix_user_email", "user", ["email"])

    op.create_table(
        "engagement",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("storycluster.id"), nullable=False),
        sa.Column("action", sa.String, nullable=False),
        sa.Column("read_time_sec", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )

    op.create_table(
        "briefing",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("user.id"), nullable=False),
        sa.Column("content_html", sa.String, nullable=False, server_default=""),
        sa.Column("content_text", sa.String, nullable=False, server_default=""),
        sa.Column("story_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sent", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("briefing")
    op.drop_table("engagement")
    op.drop_table("user")
    op.drop_table("perspective")
    op.drop_table("article")
    op.drop_table("storycluster")
    op.drop_index("ix_source_name", table_name="source")
    op.drop_table("source")
