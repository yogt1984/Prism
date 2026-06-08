"""Add source lifecycle fields.

Revision ID: 009
Revises: 008
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"


def upgrade() -> None:
    with op.batch_alter_table("source") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(), server_default="candidate", nullable=False)
        )
        batch_op.add_column(
            sa.Column("discovered_via", sa.String(), server_default="", nullable=False)
        )
        batch_op.add_column(
            sa.Column("probation_start", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("articles_validated", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("articles_failed", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("sighting_count", sa.Integer(), server_default="0", nullable=False)
        )
        batch_op.add_column(
            sa.Column("last_evaluated", sa.DateTime(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("rejection_reason", sa.String(), server_default="", nullable=False)
        )

    # Backfill: existing seeded sources → status="seed"
    op.execute("UPDATE source SET status = 'seed' WHERE trust_score >= 0.5")


def downgrade() -> None:
    with op.batch_alter_table("source") as batch_op:
        batch_op.drop_column("rejection_reason")
        batch_op.drop_column("last_evaluated")
        batch_op.drop_column("sighting_count")
        batch_op.drop_column("articles_failed")
        batch_op.drop_column("articles_validated")
        batch_op.drop_column("probation_start")
        batch_op.drop_column("discovered_via")
        batch_op.drop_column("status")
