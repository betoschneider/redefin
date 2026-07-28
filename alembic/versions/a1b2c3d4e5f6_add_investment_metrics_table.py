"""add_investment_metrics_table

Revision ID: a1b2c3d4e5f6
Revises: 5f9c3a7b2d1e
Create Date: 2026-07-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '5f9c3a7b2d1e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create investment_metrics table
    op.create_table('investment_metrics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('last_portfolio_value', sa.Float(), nullable=True),
        sa.Column('last_query_date', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investment_metrics_id'), 'investment_metrics', ['id'], unique=False)
    op.create_index(op.f('ix_investment_metrics_owner_id'), 'investment_metrics', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_investment_metrics_owner_id'), table_name='investment_metrics')
    op.drop_index(op.f('ix_investment_metrics_id'), table_name='investment_metrics')
    op.drop_table('investment_metrics')
