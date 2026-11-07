"""Setor da empresa para a torre multi-setorial.

Revision ID: 0005
Revises: 0004
"""

from pathlib import Path

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0005_setor_empresa.sql")


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    op.execute("ALTER TABLE empresa DROP COLUMN IF EXISTS setor")
