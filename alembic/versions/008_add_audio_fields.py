"""Add TTS audio fields to Briefing.

Revision ID: 008
Revises: 007
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"


def upgrade() -> None:
    op.add_column("briefing", sa.Column(
        "audio_path", sa.String(), server_default="", nullable=False))
    op.add_column("briefing", sa.Column(
        "audio_duration_sec", sa.Integer(), server_default="0", nullable=False))
    op.add_column("briefing", sa.Column(
        "audio_size_bytes", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("briefing", "audio_size_bytes")
    op.drop_column("briefing", "audio_duration_sec")
    op.drop_column("briefing", "audio_path")
