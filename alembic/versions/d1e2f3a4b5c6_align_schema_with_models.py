"""align_schema_with_models

Alinha o esquema produzido pelas migrations ao modelo atual (app/models.py):
- cria financial_insights (com coluna ano) se não existir
- cria investment_insights se não existir
- adiciona colunas extras de users (name, email, ai_provider, api_key)
- garante a coluna ano em financial_insights de bancos legados

As checagens via inspector tornam a migration segura para bancos já criados
por create_all (que já possuem essas tabelas/colunas).

Revision ID: d1e2f3a4b5c6
Revises: c7d8e9f0a1b2
Create Date: 2026-08-10 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c7d8e9f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _colunas(bind, tabela: str) -> set[str]:
    return {c["name"] for c in sa.inspect(bind).get_columns(tabela)}


def upgrade() -> None:
    bind = op.get_bind()
    tabelas = set(sa.inspect(bind).get_table_names())

    # financial_insights (com coluna ano)
    if "financial_insights" not in tabelas:
        op.create_table(
            "financial_insights",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.Column("ano", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_financial_insights_id", "financial_insights", ["id"], unique=False)
        op.create_index("ix_financial_insights_owner_id", "financial_insights", ["owner_id"], unique=False)
        op.create_index("ix_financial_insights_ano", "financial_insights", ["ano"], unique=False)
    else:
        # Bancos legados podem não ter a coluna ano
        if "ano" not in _colunas(bind, "financial_insights"):
            op.add_column("financial_insights", sa.Column("ano", sa.Integer(), nullable=True))

    # investment_insights
    if "investment_insights" not in tabelas:
        op.create_table(
            "investment_insights",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("owner_id", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["owner_id"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_investment_insights_id", "investment_insights", ["id"], unique=False)
        op.create_index("ix_investment_insights_owner_id", "investment_insights", ["owner_id"], unique=False)

    # users: colunas extras do modelo
    if "users" in tabelas:
        colunas_users = _colunas(bind, "users")
        for nome_col, tipo in [
            ("name", sa.String()),
            ("email", sa.String()),
            ("ai_provider", sa.String()),
            ("api_key", sa.String()),
        ]:
            if nome_col not in colunas_users:
                op.add_column("users", sa.Column(nome_col, tipo, nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    tabelas = set(sa.inspect(bind).get_table_names())

    if "investment_insights" in tabelas:
        op.drop_table("investment_insights")
    if "financial_insights" in tabelas:
        op.drop_table("financial_insights")

    if "users" in tabelas:
        colunas_users = _colunas(bind, "users")
        for nome_col in ["api_key", "ai_provider", "email", "name"]:
            if nome_col in colunas_users:
                op.drop_column("users", nome_col)
