"""What a person does, and where: two optional columns on the user.

Revision ID: 5b2e8c41d7a3
Revises: 1f4631da751b
Create Date: 2026-11-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "5b2e8c41d7a3"
down_revision = "1f4631da751b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("user", sa.Column("job_title", sa.UnicodeText(), nullable=True))
    op.add_column("user", sa.Column("organization", sa.UnicodeText(), nullable=True))


def downgrade() -> None:
    op.drop_column("user", "organization")
    op.drop_column("user", "job_title")
