"""Add steps_versions table

Revision ID: 002
Revises: 001
Create Date: 2025-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add current_steps_version to jobs table
    op.add_column('jobs', sa.Column('current_steps_version', sa.Integer(), nullable=False, server_default='1'))

    # Create steps_versions table
    op.create_table(
        'steps_versions',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('jobs.id'), nullable=False),
        sa.Column('version', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('steps_json', postgresql.JSON(), nullable=False),
        sa.Column('edit_source', sa.String(50), nullable=True),
        sa.Column('edit_note', sa.Text(), nullable=True),
    )

    # Create indexes
    op.create_index('ix_steps_versions_job_id', 'steps_versions', ['job_id'])
    op.create_index('ix_steps_versions_job_version', 'steps_versions', ['job_id', 'version'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_steps_versions_job_version')
    op.drop_index('ix_steps_versions_job_id')
    op.drop_table('steps_versions')
    op.drop_column('jobs', 'current_steps_version')
