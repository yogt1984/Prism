"""Add perception tracking tables: keywordtrack, keywordmention, perceptionsnapshot.

Revision ID: 006
Revises: 005
Create Date: 2026-06-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "keywordtrack",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("keyword", sa.String, nullable=False, unique=True),
        sa.Column("aliases", sa.String, nullable=False, server_default=""),
        sa.Column("category", sa.String, nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_keywordtrack_keyword", "keywordtrack", ["keyword"])

    op.create_table(
        "keywordmention",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("keyword_id", sa.Integer, sa.ForeignKey("keywordtrack.id"), nullable=False),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("storycluster.id"), nullable=False),
        sa.Column("mention_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("headline_hit", sa.Boolean, nullable=False, server_default=sa.text("0")),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("weighted_score", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("seen_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_keywordmention_keyword_id", "keywordmention", ["keyword_id"])
    op.create_index("ix_keywordmention_cluster_id", "keywordmention", ["cluster_id"])

    op.create_table(
        "perceptionsnapshot",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("keyword_id", sa.Integer, sa.ForeignKey("keywordtrack.id"), nullable=False),
        sa.Column("perception", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("salience", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("valence", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("momentum", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("cluster_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_perceptionsnapshot_keyword_id", "perceptionsnapshot", ["keyword_id"])


def downgrade() -> None:
    op.drop_table("perceptionsnapshot")
    op.drop_table("keywordmention")
    op.drop_table("keywordtrack")
