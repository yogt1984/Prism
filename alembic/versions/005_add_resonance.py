"""Add TopicResonance table and resonance_score column to storycluster.

Revision ID: 005
Revises: 004
Create Date: 2026-05-28
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "topicresonance",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cluster_id", sa.Integer, sa.ForeignKey("storycluster.id"), nullable=False, index=True),
        sa.Column("resonance", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("momentum", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("peak_resonance", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("mention_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("source_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("authority_weighted_sum", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("breadth", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("window_hours", sa.Integer, nullable=False, server_default="72"),
        sa.Column("computed_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.add_column("storycluster", sa.Column("resonance_score", sa.Float, nullable=False, server_default="0.0"))


def downgrade() -> None:
    op.drop_column("storycluster", "resonance_score")
    op.drop_table("topicresonance")
