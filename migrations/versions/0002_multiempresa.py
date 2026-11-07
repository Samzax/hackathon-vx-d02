"""Multiempresa: obrigação própria de uma cliente, conta ligada à empresa (ou à plataforma) e
auditoria por empresa.

Revision ID: 0002
Revises: 0001
"""

from pathlib import Path

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0002_multiempresa.sql")
COLUNAS = (("auditoria", "empresa"), ("usuario", "plataforma"), ("usuario", "empresa"), ("obrigacao", "empresa"))


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    for tabela, coluna in COLUNAS:
        op.execute(f"ALTER TABLE {tabela} DROP COLUMN IF EXISTS {coluna}")
