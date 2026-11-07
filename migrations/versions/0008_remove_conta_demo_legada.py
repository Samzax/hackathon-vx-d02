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

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

EMAIL = "curadoria@regulaia.demo"
SQL = [
    f"DELETE FROM sessao WHERE usuario_id IN (SELECT id FROM usuario WHERE email = '{EMAIL}' AND criado_por = 'demo')",
    f"DELETE FROM usuario WHERE email = '{EMAIL}' AND criado_por = 'demo'",
]


def upgrade() -> None:
    for comando in SQL:
        op.execute(comando)


def downgrade() -> None:
    pass        # dado apagado não volta; a conta não existe mais no seed
