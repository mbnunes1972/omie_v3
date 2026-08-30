"""cria tabela veredictos_provisao

ACHADO-16 (docs/db/ACHADOS_CONTABEIS.md / docs/db/TAREFA_ACHADO16.md, passo 8): a Conciliação
Final parava de cancelar provisão em aberto em silêncio — cada rubrica aberta passa a exigir um
veredito NOMEADO ('efetivada' | 'encerrada_valor_menor' | 'nao_se_aplica' | 'ainda_vai_chegar'),
registrado com quem decidiu e quando. É o rastro que sustenta o relatório de "projetos encerrados
por reversão" (docs/db/TAREFA_ACHADO16.md).

Revision ID: e031f6ad9c80
Revises: 95c7e64afc6a
Create Date: 2026-08-30 12:57:34.239015

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e031f6ad9c80'
down_revision: Union[str, Sequence[str], None] = '95c7e64afc6a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'veredictos_provisao',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('owner_tipo', sa.String(length=10), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('projeto_nome', sa.Text(), nullable=False),
        sa.Column('codigo_provisao', sa.Text(), nullable=False),
        sa.Column('veredito', sa.Text(), nullable=False),
        sa.Column('valor_provisionado', sa.Float(), nullable=False),
        sa.Column('valor_efetivado', sa.Float(), nullable=True),
        sa.Column('valor_revertido', sa.Float(), nullable=True),
        sa.Column('motivo', sa.Text(), nullable=True),
        sa.Column('decidido_por_id', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('decidido_em', sa.DateTime(), nullable=True),
        sa.Column('ref', sa.String(length=80), nullable=True),
    )
    op.create_index('ix_veredictos_provisao_owner_projeto', 'veredictos_provisao',
                    ['owner_tipo', 'owner_id', 'projeto_nome'])


def downgrade() -> None:
    op.drop_index('ix_veredictos_provisao_owner_projeto', table_name='veredictos_provisao')
    op.drop_table('veredictos_provisao')
