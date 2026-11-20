"""Asking to join a community open on request.

Revision ID: 8d2e0f4a5b3c
Revises: 7c1d9e3f4a2b
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "8d2e0f4a5b3c"
down_revision = "7c1d9e3f4a2b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "community_membership_request",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "community_id",
            sa.Integer(),
            sa.ForeignKey("community.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("community_id", "user_id"),
    )


def downgrade() -> None:
    op.drop_table("community_membership_request")
