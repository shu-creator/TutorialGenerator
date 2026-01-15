"""Add theme_json to jobs table

Revision ID: 003
Revises: 002
Create Date: 2026-01-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add theme_json column to jobs table
    # NULL means default theme will be used
    op.add_column('jobs', sa.Column('theme_json', postgresql.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('jobs', 'theme_json')
