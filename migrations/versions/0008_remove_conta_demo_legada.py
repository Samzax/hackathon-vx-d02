"""Remove a conta da demo do nome antigo: curadoria@regulaia.demo.

O rename RegulaIA → Mitra trocou o e-mail da conta da curadoria da demo para curadoria@mitra.demo; o
seed cria a nova e não toca na antiga, que ficava no banco como um segundo login de plataforma com a
mesma senha da demo. Pedido do usuário (7/11/2026): apagar.

Só a conta criada pelo seed (criado_por = 'demo'). A sessão aponta para o usuário por chave estrangeira
e vai antes; a auditoria guarda o e-mail como texto e fica como está (o histórico continua legível).
Sem volta: o downgrade não recria a conta (o seed atual não a conhece).

Revision ID: 0008
Revises: 0007
"""

from pathlib import Path

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

SQL = Path(__file__).with_name("0008_remove_conta_demo_legada.sql")


def upgrade() -> None:
    op.execute(SQL.read_text(encoding="utf-8"))


def downgrade() -> None:
    pass        # dado apagado não volta; a conta não existe mais no seed
