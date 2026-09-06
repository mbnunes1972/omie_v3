"""fase financeira do contrato — F2-28 Passo 4

docs/db/PLANO_AJUSTES.md, princípio #5 (05/09, DECIDIDO): a Aprovação Financeira (AF1/AF2)
passa a ser revisável livremente enquanto a fase FINANCEIRA do contrato não fechar — distinta
de `Contrato.status` (que continua "vigente" e segue governando o avanço do ciclo, intocado).
Duas colunas, ambas NULL para todo contrato existente (= fase financeira ainda aberta):
  - financeiro_concluido_em (quando — setado só por POST .../contrato/concluir-financeiro,
    que confere consistência antes de fechar)
  - financeiro_concluido_por_id (quem)

Revision ID: c2d3e4f5a6b7
Revises: a1f2e3c4d5b6
Create Date: 2026-09-05 22:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2d3e4f5a6b7'
down_revision: Union[str, Sequence[str], None] = 'a1f2e3c4d5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('contratos', sa.Column('financeiro_concluido_em', sa.DateTime(), nullable=True))
    op.add_column('contratos', sa.Column('financeiro_concluido_por_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_contratos_financeiro_concluido_por', 'contratos', 'usuarios',
                          ['financeiro_concluido_por_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_contratos_financeiro_concluido_por', 'contratos', type_='foreignkey')
    op.drop_column('contratos', 'financeiro_concluido_por_id')
    op.drop_column('contratos', 'financeiro_concluido_em')
