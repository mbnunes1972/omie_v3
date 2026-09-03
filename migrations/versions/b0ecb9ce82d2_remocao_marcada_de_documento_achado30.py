"""remocao marcada de documento de fase — ACHADO-30

docs/db/ACHADOS_CONTABEIS.md, ACHADO-30 / docs/db/TAREFA_BLOCO_FISCAL.md item 1
(DECIDIDO 03/09): enquanto a fase está aberta o documento pode ser marcado como removido;
depois que fecha, imutável. Remover NÃO apaga — nem o registro nem o arquivo em disco: a
promessa append-only de `ciclo_documentos` continua de pé e o rastro de que houve tentativa
não some. Duas colunas, ambas NULL para todo documento existente (= vivo):
  - removido_em (quando)
  - removido_por_id (quem)

Revision ID: b0ecb9ce82d2
Revises: 82275b998a4a
Create Date: 2026-09-03 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b0ecb9ce82d2'
down_revision: Union[str, Sequence[str], None] = '82275b998a4a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('ciclo_documentos', sa.Column('removido_em', sa.DateTime(), nullable=True))
    op.add_column('ciclo_documentos', sa.Column('removido_por_id', sa.Integer(), nullable=True))
    op.create_foreign_key('fk_ciclo_documentos_removido_por', 'ciclo_documentos', 'usuarios',
                          ['removido_por_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint('fk_ciclo_documentos_removido_por', 'ciclo_documentos', type_='foreignkey')
    op.drop_column('ciclo_documentos', 'removido_por_id')
    op.drop_column('ciclo_documentos', 'removido_em')
