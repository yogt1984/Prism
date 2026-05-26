"""Add prompt_version column to storycluster and briefing.

Revision ID: 003
Revises: 002
Create Date: 2026-05-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("storycluster", sa.Column("prompt_version", sa.String, nullable=False, server_default=""))
    op.add_column("briefing", sa.Column("prompt_version", sa.String, nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("briefing", "prompt_version")
    op.drop_column("storycluster", "prompt_version")
