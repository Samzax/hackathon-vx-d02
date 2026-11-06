"""Esquema inicial: as tabelas da torre, mais auditoria e sessão da API.

Revision ID: 0001
Revises:
"""

from pathlib import Path

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0001_esquema_inicial.sql")
TABELAS = ("sessao", "auditoria", "usuario", "evento", "responsavel_obrigacao", "analise_ia", "acionamento",
           "evidencia", "obrigacao_versao", "obrigacao", "ato", "ativo", "empresa")


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    for t in TABELAS:
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
