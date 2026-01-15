"""Add transcript_uri column to jobs table.

Revision ID: 005
Revises: 004
Create Date: 2026-01-15

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add transcript_uri column for storing transcript segments in S3
    op.add_column("jobs", sa.Column("transcript_uri", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("jobs", "transcript_uri")
