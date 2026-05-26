"""Add quality_score column to storycluster.

Revision ID: 004
Revises: 003
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("storycluster", sa.Column("quality_score", sa.Float, nullable=False, server_default="0.0"))


def downgrade() -> None:
    op.drop_column("storycluster", "quality_score")
