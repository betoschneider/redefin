"""add_investment_history

Adiciona a tabela investment_history para armazenar o histórico diário da
carteira (1 linha por dia por usuário), usada pelo gráfico de evolução.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-08-14 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2f3a4b5c6d7'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('investment_history',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=True),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('yield_pct', sa.Float(), nullable=True),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_investment_history_id'), 'investment_history', ['id'], unique=False)
    op.create_index(op.f('ix_investment_history_owner_id'), 'investment_history', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_investment_history_owner_id'), table_name='investment_history')
    op.drop_index(op.f('ix_investment_history_id'), table_name='investment_history')
    op.drop_table('investment_history')
