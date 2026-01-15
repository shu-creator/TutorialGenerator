"""Add indexes for job list queries.

Revision ID: 004
Revises: 003
Create Date: 2026-01-15

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Index for filtering by status
    op.create_index("ix_jobs_status", "jobs", ["status"])

    # Index for sorting by created_at
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    # Index for title search (partial matching via LIKE)
    op.create_index("ix_jobs_title", "jobs", ["title"])

    # Composite index for common query patterns (status + created_at for filtered listing)
    op.create_index("ix_jobs_status_created_at", "jobs", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_jobs_status_created_at", table_name="jobs")
    op.drop_index("ix_jobs_title", table_name="jobs")
    op.drop_index("ix_jobs_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status", table_name="jobs")
