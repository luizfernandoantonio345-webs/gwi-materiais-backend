"""add usuario.foto

Revision ID: a1c2d3e4f5a6
Revises: 43b7d1e418d0
Create Date: 2026-09-08 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c2d3e4f5a6'
down_revision: Union[str, None] = '43b7d1e418d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('usuarios', sa.Column('foto', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('usuarios', 'foto')
