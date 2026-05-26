"""Add datetime indexes for time-range queries.

Revision ID: 002
Revises: 001
Create Date: 2026-05-25
"""
from typing import Sequence, Union

from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("ix_storycluster_first_seen", "storycluster", ["first_seen"])
    op.create_index("ix_article_fetched_at", "article", ["fetched_at"])
    op.create_index("ix_briefing_created_at", "briefing", ["created_at"])
    op.create_index("ix_engagement_created_at", "engagement", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_engagement_created_at", table_name="engagement")
    op.drop_index("ix_briefing_created_at", table_name="briefing")
    op.drop_index("ix_article_fetched_at", table_name="article")
    op.drop_index("ix_storycluster_first_seen", table_name="storycluster")
