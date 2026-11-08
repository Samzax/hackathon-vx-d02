"""Resumo da análise de cada ato no banco (tabela analise_ato).

Antes ficava num arquivo do container (data/radar_demo.json), que todo deploy apagava.

Revision ID: 0009
Revises: 0008
"""

from pathlib import Path

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0009_analise_ato.sql")


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS analise_ato")
