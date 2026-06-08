"""Add Stripe subscription fields to User and StripeEvent table.

Revision ID: 007
Revises: 006
Create Date: 2026-06-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Stripe fields to User
    op.add_column("user", sa.Column("stripe_customer_id", sa.String(), server_default="", nullable=False))
    op.add_column("user", sa.Column("stripe_subscription_id", sa.String(), server_default="", nullable=False))
    op.add_column("user", sa.Column("pro_since", sa.DateTime(), nullable=True))
    op.add_column("user", sa.Column("pro_until", sa.DateTime(), nullable=True))

    # Create StripeEvent table
    op.create_table(
        "stripeevent",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("event_id", sa.String(), nullable=False, unique=True),
        sa.Column("event_type", sa.String(), server_default="", nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("user.id"), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_stripeevent_event_id", "stripeevent", ["event_id"])


def downgrade() -> None:
    op.drop_table("stripeevent")
    op.drop_column("user", "pro_until")
    op.drop_column("user", "pro_since")
    op.drop_column("user", "stripe_subscription_id")
    op.drop_column("user", "stripe_customer_id")
