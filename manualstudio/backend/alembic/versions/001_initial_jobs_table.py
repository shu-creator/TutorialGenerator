"""Initial jobs table

Revision ID: 001
Revises:
Create Date: 2025-01-14

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create job status enum
    job_status = postgresql.ENUM(
        'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED',
        name='jobstatus'
    )
    job_status.create(op.get_bind())

    # Create jobs table
    op.create_table(
        'jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),

        # Status and progress
        sa.Column('status', postgresql.ENUM('QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED', name='jobstatus', create_type=False), nullable=False),
        sa.Column('stage', sa.String(50), nullable=True),
        sa.Column('progress', sa.Integer(), nullable=False, default=0),

        # Input parameters
        sa.Column('title', sa.String(255), nullable=True),
        sa.Column('goal', sa.Text(), nullable=True),
        sa.Column('language', sa.String(10), nullable=False, default='ja'),

        # Video metadata
        sa.Column('video_duration_sec', sa.Float(), nullable=True),
        sa.Column('video_fps', sa.Float(), nullable=True),
        sa.Column('video_resolution', sa.String(20), nullable=True),

        # Storage URIs
        sa.Column('input_video_uri', sa.String(500), nullable=True),
        sa.Column('audio_uri', sa.String(500), nullable=True),
        sa.Column('steps_json_uri', sa.String(500), nullable=True),
        sa.Column('pptx_uri', sa.String(500), nullable=True),
        sa.Column('frames_prefix_uri', sa.String(500), nullable=True),

        # Processing metadata
        sa.Column('transcription_provider', sa.String(50), nullable=True),
        sa.Column('llm_provider', sa.String(50), nullable=True),
        sa.Column('transcript_segments', postgresql.JSON(), nullable=True),
        sa.Column('candidate_frames', postgresql.JSON(), nullable=True),

        # Error handling
        sa.Column('error_code', sa.String(100), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('trace_id', sa.String(50), nullable=True),
    )

    # Create indexes
    op.create_index('ix_jobs_status', 'jobs', ['status'])
    op.create_index('ix_jobs_created_at', 'jobs', ['created_at'])


def downgrade() -> None:
    op.drop_index('ix_jobs_created_at')
    op.drop_index('ix_jobs_status')
    op.drop_table('jobs')

    # Drop enum
    job_status = postgresql.ENUM(
        'QUEUED', 'RUNNING', 'SUCCEEDED', 'FAILED', 'CANCELED',
        name='jobstatus'
    )
    job_status.drop(op.get_bind())
