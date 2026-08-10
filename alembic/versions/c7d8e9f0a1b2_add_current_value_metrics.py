"""add_current_value_metrics

Adiciona colunas current_value/current_date à investment_metrics para
separar a referência do dia anterior (last_*) do último valor consultado.

Revision ID: c7d8e9f0a1b2
Revises: a1b2c3d4e5f6
Create Date: 2026-08-10 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('investment_metrics', sa.Column('current_value', sa.Float(), nullable=True))
    op.add_column('investment_metrics', sa.Column('current_date', sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column('investment_metrics', 'current_date')
    op.drop_column('investment_metrics', 'current_value')
