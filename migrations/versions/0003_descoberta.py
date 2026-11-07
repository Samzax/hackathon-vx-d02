"""Descoberta de normas: a fila de normas candidatas e até onde cada fonte oficial foi lida.

Revision ID: 0003
Revises: 0002
"""

from pathlib import Path

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0003_descoberta.sql")


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS descoberta_busca")
    op.execute("DROP TABLE IF EXISTS norma_candidata")
