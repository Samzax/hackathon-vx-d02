"""Instanciação de empresa: etapas, unidades, licenças e condicionantes, responsáveis técnicos
(CPF cifrado), prazo interno, escopo por unidade e o código da obrigação único por empresa.

Revision ID: 0006
Revises: 0005
"""

from pathlib import Path

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0006_instanciacao.sql")


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    for tabela in ("responsavel_padrao", "prazo_interno", "responsavel_tecnico", "condicionante",
                   "licenca", "unidade", "instanciacao_evento", "instanciacao"):
        op.execute(f"DROP TABLE IF EXISTS {tabela}")
    op.execute("DROP INDEX IF EXISTS obrigacao_empresa_codigo")
    op.execute("ALTER TABLE obrigacao ADD CONSTRAINT obrigacao_codigo_key UNIQUE (codigo)")
    op.execute("ALTER TABLE usuario DROP COLUMN IF EXISTS unidades")
    op.execute("ALTER TABLE usuario DROP COLUMN IF EXISTS trocar_senha")
    op.execute("ALTER TABLE ativo DROP COLUMN IF EXISTS unidade")
